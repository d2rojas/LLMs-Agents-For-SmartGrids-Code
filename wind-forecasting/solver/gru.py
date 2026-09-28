"""The conventional forecaster: a GRU per horizon, correcting the evaluation protocol's reference model.

The paper names a GRU as the conventional baseline. Two things about this one are worth
knowing before reading its numbers, because both were learned from a first version that
performed badly and are the reason it is built this way.

**It knows the time of day.** The first version had no clock, and every window it is asked about
at test time starts at midnight while its training windows started at every hour of the day. At 48
hours that hardly matters; at 3 hours the daily cycle is most of what is left to predict once the
last measurement has been used, and the model lost to a two-parameter reference on fourteen of the
twenty evaluation windows. The sine and cosine of the time of day are now two of its inputs.

**One model per horizon.** The first version predicted 48 hours in one shot and the shorter
horizons were read off its first values. That is the wrong objective: averaged over two days
the best square-error prediction is close to the mean, so the network learned a nearly flat
curve (it varied by 28 kW where the measurements varied by 181 kW) and threw away the short
horizons, where the last measured value carries almost all the information. Each horizon now
has its own model, trained on its own objective.

**It predicts the residual, not the level.** The target is the difference between the
measurement and the reference model of the ANEMOS protocol
(``solver/reference.py``: ``a_k P(t) + (1 - a_k) Pbar``, fitted on the training period). A
model that learns nothing therefore reproduces the reference exactly, and whatever it does
learn is added value that the protocol's improvement score measures honestly. Predicting the
level instead lets a network score well while being worse than a model that costs nothing,
which is exactly what happened before.

Training data is days 1 to 214 of every complete turbine of the farm, twenty-nine of them, not
only the five in the benchmark: more data, and no leakage, because the day bound is what keeps
a target day out, and turbines of one farm share their weather. Days 2 to 200 train, 201 to 214
validate and choose the stopping epoch, and no target day is ever read.

    python run.py train-gru --force     # writes data/gru/gru_v1.json

At run time it is one of the tools of ``solver/tools.py``; no method calls it in any other way,
and the rule-based row is exactly "parser + this tool".
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import FEATURES, HORIZONS_H, PROJECT_ROOT, RATED_KW, STEPS_PER_HOUR, TRAIN_LAST_DAY
from solver.data import abnormal_mask

GRU_DIR = PROJECT_ROOT / "data" / "gru"
WEIGHTS_PATH = GRU_DIR / "gru_v1.json"
INPUT_STEPS = 144                      # 24 h of history
HIDDEN = 64
SCALE = {"Wspd": 25.0, "Wdir": 180.0, "Etmp": 50.0, "Patv": RATED_KW}
VAL_FIRST_DAY = 201
STRIDE = {3: 12, 6: 12, 48: 18}        # how far apart the training windows start, per horizon


# ------------------------------------------------------------------ features


N_FEATURES = 7   # the four SCADA columns, a validity flag, and the clock


def feature_matrix(frame: pd.DataFrame, rating_kw: float = RATED_KW) -> np.ndarray:
    """(n, 7): the four features in units of the turbine's rating, a validity flag, and the time of day.

    Power is divided by the rating of the turbine the window belongs to, not by a constant, so a
    turbine of another size is read correctly rather than as an out-of-scale one.

    The last two columns are the sine and cosine of the time of day. Without them the network has
    no clock, and it showed: the first version was asked at test time for forecasts that all start
    at midnight, while its training windows started at every hour, so it could not place itself in
    the daily cycle. That cost it the short horizon, where the cycle is most of what is left to
    predict once the last measurement is used."""
    x = np.zeros((len(frame), N_FEATURES), dtype=np.float32)
    valid = np.ones(len(frame), dtype=np.float32)
    scale = dict(SCALE, Patv=float(rating_kw))
    for j, c in enumerate(FEATURES):
        col = pd.to_numeric(frame[c], errors="coerce")
        valid *= col.notna().to_numpy(dtype=np.float32)
        col = col.ffill().bfill().fillna(0.0)
        x[:, j] = (col.to_numpy(dtype=np.float32) / scale[c])
    x[:, 3] = np.clip(x[:, 3], 0.0, 1.2)
    x[:, 4] = valid
    parts = frame["Tmstamp"].astype(str).str.split(":", expand=True).astype(int)
    frac = ((parts[0] * 60 + parts[1]) / 1440.0).to_numpy(dtype=np.float32)
    x[:, 5] = np.sin(2 * np.pi * frac)
    x[:, 6] = np.cos(2 * np.pi * frac)
    return x


def _model(out_steps: int, hidden: int = HIDDEN):
    import torch
    import torch.nn as nn

    class Net(nn.Module):
        """Reads 24 h and writes the correction to apply to the reference forecast, in units of rated power."""

        def __init__(self) -> None:
            super().__init__()
            self.gru = nn.GRU(N_FEATURES, hidden, batch_first=True)
            self.head = nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, out_steps))

        def forward(self, x):  # type: ignore[override]
            _, h = self.gru(x)
            return torch.tanh(self.head(h[-1]))   # a correction in [-1, 1] of rated power

    return Net()


# ------------------------------------------------------------------ training


def _samples(frame: pd.DataFrame, turbine_ref: Dict[str, Any], first_day: int, last_day: int, horizon_h: int, stride: int):
    """Windows of one turbine: inputs, the reference forecast, the measurement and its scoring mask."""
    out_steps = horizon_h * STEPS_PER_HOUR
    f = frame[(frame["Day"] >= first_day - 1) & (frame["Day"] <= last_day)].reset_index(drop=True)
    x = feature_matrix(f)
    p = pd.to_numeric(f["Patv"], errors="coerce").clip(lower=0)
    y = p.to_numpy(dtype=np.float32) / RATED_KW
    p_filled = p.ffill().bfill().fillna(0.0).to_numpy(dtype=np.float32) / RATED_KW
    mask = (~abnormal_mask(f)).to_numpy(dtype=np.float32) * np.isfinite(y)
    day = f["Day"].to_numpy()
    a = np.asarray(turbine_ref["a_k"][:out_steps], dtype=np.float32)
    pbar = np.float32(turbine_ref["mean_kw"] / RATED_KW)
    X, R, Y, M = [], [], [], []
    for start in range(0, len(f) - INPUT_STEPS - out_steps + 1, stride):
        end = start + INPUT_STEPS
        if day[end] < first_day:
            continue
        X.append(x[start:end])
        R.append(a * p_filled[end - 1] + (1.0 - a) * pbar)   # the reference, from the last measured value
        Y.append(np.nan_to_num(y[end:end + out_steps]))
        M.append(mask[end:end + out_steps])
    if not X:
        return None
    return np.stack(X), np.stack(R), np.stack(Y), np.stack(M)


def _train_one(horizon_h: int, data: Dict[str, Any], *, epochs: int, lr: float, batch: int, seed: int, log) -> Dict[str, Any]:
    import torch

    torch.manual_seed(seed)
    out_steps = horizon_h * STEPS_PER_HOUR
    Xtr, Rtr, Ytr, Mtr = data["train"]
    Xva, Rva, Yva, Mva = data["val"]
    ref_mae = float((np.abs(Rva - Yva) * Mva).sum() / max(Mva.sum(), 1.0)) * RATED_KW
    log(f"  {horizon_h:2d} h: {len(Xtr)} training windows, {len(Xva)} validation windows; the reference scores {ref_mae:.1f} kW on them")
    net = _model(out_steps)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    t_Xva, t_Rva, t_Yva, t_Mva = (torch.from_numpy(v) for v in (Xva, Rva, Yva, Mva))
    best, best_state, history = math.inf, None, []
    t0 = time.time()
    for ep in range(1, epochs + 1):
        net.train()
        perm = np.random.RandomState(seed + ep).permutation(len(Xtr))
        tot, nb = 0.0, 0
        for i in range(0, len(perm), batch):
            idx = perm[i:i + batch]
            xb = torch.from_numpy(Xtr[idx]); rb = torch.from_numpy(Rtr[idx])
            yb = torch.from_numpy(Ytr[idx]); mb = torch.from_numpy(Mtr[idx])
            pred = torch.clamp(rb + net(xb), 0.0, 1.05)
            loss = (((pred - yb) ** 2) * mb).sum() / mb.sum().clamp(min=1.0)
            opt.zero_grad(); loss.backward(); opt.step()
            tot += float(loss); nb += 1
        net.eval()
        with torch.no_grad():
            pv = torch.clamp(t_Rva + net(t_Xva), 0.0, 1.05)
            mae = float(((pv - t_Yva).abs() * t_Mva).sum() / t_Mva.sum().clamp(min=1.0)) * RATED_KW
        imp = 100.0 * (ref_mae - mae) / ref_mae
        history.append({"epoch": ep, "train_mse_norm": round(tot / max(nb, 1), 6), "val_mae_kw": round(mae, 1), "val_improvement_pct": round(imp, 2)})
        log(f"    epoch {ep:2d}  val MAE {mae:6.1f} kW   improvement over the reference {imp:+5.1f} %   ({time.time() - t0:.0f} s)")
        if mae < best:
            best, best_state = mae, {k: v.detach().cpu().numpy().tolist() for k, v in net.state_dict().items()}
    return {"out_steps": out_steps, "hidden": HIDDEN, "best_val_mae_kw": round(best, 1),
            "reference_val_mae_kw": round(ref_mae, 1), "best_val_improvement_pct": round(100.0 * (ref_mae - best) / ref_mae, 2),
            "epochs": epochs, "history": history, "state": best_state}


def train(*, epochs: int = 8, seed: int = 0, lr: float = 1e-3, batch: int = 256, force: bool = False, log=print) -> Path:
    import torch

    from solver import reference as R

    if WEIGHTS_PATH.exists() and not force:
        raise FileExistsError(f"{WEIGHTS_PATH} exists; pass --force to retrain")
    np.random.seed(seed)
    files = sorted(GRU_DIR.glob("train_t*.csv.gz"))
    if not files:
        raise FileNotFoundError("no data/gru/train_t*.csv.gz; run `python run.py freeze-data` first")
    params = R.parameters()["turbines"]
    frames, hashes = {}, {}
    for p in files:
        t = p.name.split("_t")[1].split(".")[0]
        if str(int(t)) not in params:
            log(f"  skipping {p.name}: no reference parameters")
            continue
        hashes[p.name] = "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
        frames[str(int(t))] = pd.read_csv(p)
    log(f"{len(frames)} turbines, days 2 to {VAL_FIRST_DAY - 1} to train and {VAL_FIRST_DAY} to {TRAIN_LAST_DAY} to validate")

    horizons: Dict[str, Any] = {}
    for h in HORIZONS_H:
        parts: Dict[str, List[np.ndarray]] = {"train": [], "val": []}
        for t, df in frames.items():
            for split, (a, b, st) in (("train", (2, VAL_FIRST_DAY - 1, STRIDE[h])), ("val", (VAL_FIRST_DAY, TRAIN_LAST_DAY, STRIDE[h] * 2))):
                got = _samples(df, params[t], a, b, h, st)
                if got is not None:
                    parts[split].append(got)
        data = {k: tuple(np.concatenate([p[i] for p in v]) for i in range(4)) for k, v in parts.items()}
        horizons[str(h)] = _train_one(h, data, epochs=epochs, lr=lr, batch=batch, seed=seed, log=log)

    GRU_DIR.mkdir(parents=True, exist_ok=True)
    WEIGHTS_PATH.write_text(json.dumps({
        "model": "one GRU(5 -> 64) + MLP head per horizon, 24 h in, predicting the correction to the ANEMOS reference model",
        "input_steps": INPUT_STEPS, "features": list(FEATURES) + ["valid", "sin_time_of_day", "cos_time_of_day"], "scale": SCALE, "rated_kw": RATED_KW,
        "reference": "solver/reference.py, a_k P(t) + (1 - a_k) Pbar, fitted on days 1 to 214",
        "training": {"turbines": sorted(int(t) for t in frames), "n_turbines": len(frames), "train_days": [2, VAL_FIRST_DAY - 1],
                     "val_days": [VAL_FIRST_DAY, TRAIN_LAST_DAY], "stride": STRIDE, "epochs": epochs, "seed": seed, "lr": lr, "batch": batch,
                     "train_file_hashes": hashes, "torch": torch.__version__, "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "note": "no target day (215 onwards) is read anywhere in this file"},
        "horizons": horizons,
    }), encoding="utf-8")
    for h, v in horizons.items():
        log(f"  {h:>2} h: validation MAE {v['best_val_mae_kw']} kW against the reference's {v['reference_val_mae_kw']} kW "
            f"({v['best_val_improvement_pct']:+.1f} %)")
    log(f"wrote {WEIGHTS_PATH.relative_to(PROJECT_ROOT)}")
    return WEIGHTS_PATH


# ------------------------------------------------------------------ inference

_CACHE: Dict[str, Any] = {}


def weights_hash() -> Optional[str]:
    return ("sha256:" + hashlib.sha256(WEIGHTS_PATH.read_bytes()).hexdigest()[:16]) if WEIGHTS_PATH.exists() else None


def _load(horizon_h: int):
    import torch

    key = str(int(horizon_h))
    if key in _CACHE:
        return _CACHE[key]
    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(f"{WEIGHTS_PATH} missing; run `python run.py train-gru`")
    payload = _CACHE.get("_payload") or json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
    _CACHE["_payload"] = payload
    h = payload["horizons"].get(key)
    if h is None:
        raise KeyError(f"no model for a {horizon_h} h horizon; trained: {sorted(payload['horizons'])}")
    net = _model(h["out_steps"], h.get("hidden", HIDDEN))
    net.load_state_dict({k: torch.tensor(v) for k, v in h["state"].items()})
    net.eval()
    _CACHE[key] = net
    return net


def metadata() -> Dict[str, Any]:
    payload = _CACHE.get("_payload")
    if payload is None:
        payload = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8")) if WEIGHTS_PATH.exists() else {}
        _CACHE["_payload"] = payload
    return {k: v for k, v in payload.items() if k != "horizons"} | {
        "horizons": {k: {kk: vv for kk, vv in v.items() if kk != "state"} for k, v in (payload.get("horizons") or {}).items()}}


def forecast(window: Any, horizon_h: int) -> List[float]:
    """The reference forecast for this window plus the correction the model of that horizon writes."""
    import torch

    from solver import reference as R

    net = _load(horizon_h)
    rating = float(getattr(window, "rating_kw", RATED_KW))
    hist = window.history(days=2).tail(INPUT_STEPS).reset_index(drop=True)
    if len(hist) < INPUT_STEPS:
        raise ValueError(f"the forecaster needs {INPUT_STEPS} history rows, got {len(hist)}")
    ref = np.asarray(R.new_reference_forecast(window, horizon_h), dtype=np.float32) / rating
    x = torch.from_numpy(feature_matrix(hist, rating)).unsqueeze(0)
    with torch.no_grad():
        y = torch.clamp(torch.from_numpy(ref) + net(x)[0], 0.0, 1.0).numpy() * rating
    return [round(float(v), 1) for v in y]
