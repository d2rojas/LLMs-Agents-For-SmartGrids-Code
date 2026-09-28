"""The conventional forecaster: a small GRU trained once on the KDD Cup training period.

The paper names a GRU as the conventional baseline. This one reads the last 24 hours of
the four SCADA features and writes the next 48 hours of active power in one shot,
trained on days 1 to 200 of the five benchmark turbines, validated on days 201 to 214,
never shown a target day. Its weights are stored as JSON under ``data/gru/`` with the
training configuration and the hash of the training slices, so a run can verify it is
using the frozen model and anyone can retrain it with one command:

    python run.py train-gru            # writes data/gru/gru_v1.json (refuses to overwrite without --force)

At run time it is one of the tools of ``solver/tools.py``; no method calls it in any
other way, and the rule-based row is exactly "parser + this tool".
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

from config import FEATURES, MAX_HORIZON_H, PROJECT_ROOT, RATED_KW, STEPS_PER_HOUR, TRAIN_LAST_DAY
from solver.data import abnormal_mask

GRU_DIR = PROJECT_ROOT / "data" / "gru"
WEIGHTS_PATH = GRU_DIR / "gru_v1.json"
INPUT_STEPS = 144                      # 24 h of history
OUTPUT_STEPS = MAX_HORIZON_H * STEPS_PER_HOUR   # 288
HIDDEN = 64
SCALE = {"Wspd": 25.0, "Wdir": 180.0, "Etmp": 50.0, "Patv": RATED_KW}
VAL_FIRST_DAY = 201


# ------------------------------------------------------------------ features


def feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    """(n, 5): the four scaled features, forward-filled, plus a validity flag."""
    x = np.zeros((len(frame), 5), dtype=np.float32)
    valid = np.ones(len(frame), dtype=np.float32)
    for j, c in enumerate(FEATURES):
        col = pd.to_numeric(frame[c], errors="coerce")
        valid *= col.notna().to_numpy(dtype=np.float32)
        col = col.ffill().bfill().fillna(0.0)
        x[:, j] = (col.to_numpy(dtype=np.float32) / SCALE[c])
    x[:, 3] = np.clip(x[:, 3], 0.0, 1.2)
    x[:, 4] = valid
    return x


def _model(hidden: int = HIDDEN):
    import torch
    import torch.nn as nn

    class Net(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.gru = nn.GRU(5, hidden, batch_first=True)
            self.head = nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, OUTPUT_STEPS))

        def forward(self, x):  # type: ignore[override]
            _, h = self.gru(x)
            return torch.sigmoid(self.head(h[-1])) * 1.05   # normalised power, a little above rated

    return Net()


# ------------------------------------------------------------------ training


def _samples(frame: pd.DataFrame, first_day: int, last_day: int, stride: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    f = frame[(frame["Day"] >= first_day - 1) & (frame["Day"] <= last_day)].reset_index(drop=True)
    x = feature_matrix(f)
    y = pd.to_numeric(f["Patv"], errors="coerce").clip(lower=0).to_numpy(dtype=np.float32) / RATED_KW
    mask = (~abnormal_mask(f)).to_numpy(dtype=np.float32)
    day = f["Day"].to_numpy()
    X, Y, M = [], [], []
    for start in range(0, len(f) - INPUT_STEPS - OUTPUT_STEPS + 1, stride):
        end = start + INPUT_STEPS
        if day[end] < first_day:
            continue
        X.append(x[start:end])
        Y.append(np.nan_to_num(y[end:end + OUTPUT_STEPS]))
        M.append(mask[end:end + OUTPUT_STEPS])
    return np.stack(X), np.stack(Y), np.stack(M)


def train(*, epochs: int = 12, stride: int = 6, seed: int = 0, lr: float = 1e-3, batch: int = 256, force: bool = False, log=print) -> Path:
    import torch

    if WEIGHTS_PATH.exists() and not force:
        raise FileExistsError(f"{WEIGHTS_PATH} exists; pass --force to retrain")
    torch.manual_seed(seed)
    np.random.seed(seed)
    files = sorted(GRU_DIR.glob("train_t*.csv"))
    if not files:
        raise FileNotFoundError("no data/gru/train_t*.csv; run data/freeze.py first")
    Xtr, Ytr, Mtr, Xva, Yva, Mva = [], [], [], [], [], []
    hashes = {}
    for p in files:
        hashes[p.name] = "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
        df = pd.read_csv(p)
        a, b, c = _samples(df, 2, VAL_FIRST_DAY - 1, stride)
        Xtr.append(a); Ytr.append(b); Mtr.append(c)
        a, b, c = _samples(df, VAL_FIRST_DAY, TRAIN_LAST_DAY, stride * 2)
        Xva.append(a); Yva.append(b); Mva.append(c)
    Xtr, Ytr, Mtr = (np.concatenate(v) for v in (Xtr, Ytr, Mtr))
    Xva, Yva, Mva = (np.concatenate(v) for v in (Xva, Yva, Mva))
    log(f"training samples {len(Xtr)}, validation samples {len(Xva)} from {len(files)} turbines")
    net = _model()
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    Xtr_t, Ytr_t, Mtr_t = (torch.tensor(v) for v in (Xtr, Ytr, Mtr))
    Xva_t, Yva_t, Mva_t = (torch.tensor(v) for v in (Xva, Yva, Mva))
    best, best_state, history = math.inf, None, []
    t0 = time.time()
    for ep in range(1, epochs + 1):
        net.train()
        perm = torch.randperm(len(Xtr_t))
        tot, nb = 0.0, 0
        for i in range(0, len(perm), batch):
            idx = perm[i:i + batch]
            pred = net(Xtr_t[idx])
            m = Mtr_t[idx]
            loss = (((pred - Ytr_t[idx]) ** 2) * m).sum() / m.sum().clamp(min=1.0)
            opt.zero_grad(); loss.backward(); opt.step()
            tot += float(loss); nb += 1
        net.eval()
        with torch.no_grad():
            pv = net(Xva_t)
            mae = float((((pv - Yva_t).abs()) * Mva_t).sum() / Mva_t.sum().clamp(min=1.0)) * RATED_KW
            rmse = math.sqrt(float((((pv - Yva_t) ** 2) * Mva_t).sum() / Mva_t.sum().clamp(min=1.0))) * RATED_KW
        history.append({"epoch": ep, "train_mse_norm": round(tot / max(nb, 1), 5), "val_mae_kw": round(mae, 1), "val_rmse_kw": round(rmse, 1)})
        log(f"epoch {ep:2d}  train mse {tot / max(nb, 1):.5f}  val MAE {mae:6.1f} kW  RMSE {rmse:6.1f} kW  ({time.time() - t0:.0f} s)")
        if mae < best:
            best = mae
            best_state = {k: v.detach().cpu().numpy().tolist() for k, v in net.state_dict().items()}
    GRU_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": "GRU(5 -> 64) + MLP head, 24 h in, 48 h out, one shot", "input_steps": INPUT_STEPS, "output_steps": OUTPUT_STEPS, "hidden": HIDDEN,
        "features": list(FEATURES) + ["valid"], "scale": SCALE, "training": {"turbines": [p.name for p in files], "train_days": [2, VAL_FIRST_DAY - 1],
        "val_days": [VAL_FIRST_DAY, TRAIN_LAST_DAY], "stride": stride, "epochs": epochs, "seed": seed, "lr": lr, "batch": batch,
        "best_val_mae_kw": round(best, 1), "history": history, "train_file_hashes": hashes, "torch": torch.__version__,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, "state": best_state,
    }
    WEIGHTS_PATH.write_text(json.dumps(payload), encoding="utf-8")
    log(f"wrote {WEIGHTS_PATH.relative_to(PROJECT_ROOT)} (best validation MAE {best:.1f} kW)")
    return WEIGHTS_PATH


# ------------------------------------------------------------------ inference

_CACHE: Dict[str, Any] = {}


def weights_hash() -> Optional[str]:
    return ("sha256:" + hashlib.sha256(WEIGHTS_PATH.read_bytes()).hexdigest()[:16]) if WEIGHTS_PATH.exists() else None


def load_model():
    import torch

    if "net" in _CACHE:
        return _CACHE["net"], _CACHE["meta"]
    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(f"{WEIGHTS_PATH} missing; run `python run.py train-gru`")
    payload = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
    net = _model(payload.get("hidden", HIDDEN))
    net.load_state_dict({k: torch.tensor(v) for k, v in payload["state"].items()})
    net.eval()
    meta = {k: v for k, v in payload.items() if k != "state"}
    _CACHE["net"], _CACHE["meta"] = net, meta
    return net, meta


def forecast(history: pd.DataFrame, horizon_h: int) -> List[float]:
    """The next ``horizon_h`` hours of active power (kW) from the last 24 h of ``history`` (the four features)."""
    import torch

    net, _meta = load_model()
    h = history.tail(INPUT_STEPS).reset_index(drop=True)
    if len(h) < INPUT_STEPS:
        raise ValueError(f"the GRU needs {INPUT_STEPS} history rows, got {len(h)}")
    x = torch.tensor(feature_matrix(h)).unsqueeze(0)
    with torch.no_grad():
        y = net(x)[0].numpy() * RATED_KW
    y = np.clip(y, 0.0, RATED_KW)
    return [round(float(v), 1) for v in y[: int(horizon_h) * STEPS_PER_HOUR]]
