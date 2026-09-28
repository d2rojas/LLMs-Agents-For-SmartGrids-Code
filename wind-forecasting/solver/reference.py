"""The reference forecasts every error is measured against, as the field's evaluation protocol defines them.

Madsen, Pinson, Kariniotakis, Nielsen and Nielsen, "Standardizing the Performance
Evaluation of Short-Term Wind Power Prediction Models", Wind Engineering 29(6):475-489,
2005 (the ANEMOS protocol). Two things from it are used here and nowhere invented:

* errors are normalised by the installed capacity, giving NBIAS, NMAE and NRMSE, which the
  paper names as the minimum set to report (eq. 6 and section 5.1);
* a model is compared with a reference by the improvement score
  ``I = 100 (EC_ref - EC) / EC_ref`` in per cent (eq. 14).

The reference itself is not persistence. The protocol is explicit that "comparison with
Persistence does not give a fair measure of the performance of an advanced model, since even
the use of the global mean as predictor leads to a 50% reduction in the variance of the error
compared to the error obtained with Persistence", and adopts instead the model of Nielsen,
Joensen, Madsen, Landberg and Giebel (eq. 4), which merges the two so that neither the short
horizons nor the long ones are flattered:

    P(t+k|t) = a_k * P(t) + (1 - a_k) * Pbar

with ``a_k`` the correlation between ``P(t)`` and ``P(t+k)`` and ``Pbar`` the mean production,
both estimated on the training period only (days 1 to 214), never on a target window.

``data/reference/reference_model.json`` holds ``Pbar`` and ``a_k`` per turbine, frozen by
``run.py freeze-reference`` from the same training slices the GRU is trained on, with their
content hashes. Scoring reads that file, so the reference of a row cannot drift after the fact.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config import MAX_HORIZON_H, PROJECT_ROOT, RATED_KW, STEPS_PER_HOUR, TRAIN_LAST_DAY

REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
REFERENCE_PATH = REFERENCE_DIR / "reference_model.json"
GRU_DIR = PROJECT_ROOT / "data" / "gru"
MAX_LAG = MAX_HORIZON_H * STEPS_PER_HOUR   # 288 ten-minute steps

_CACHE: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------ freezing


def _series(path: Path) -> np.ndarray:
    """The training period's active power in chronological order, negatives read as zero."""
    df = pd.read_csv(path)
    df = df[df["Day"] <= TRAIN_LAST_DAY].copy()
    df["_t"] = df["Tmstamp"].astype(str).str.split(":", expand=True).astype(int).pipe(lambda d: d[0] * 60 + d[1])
    df = df.sort_values(["Day", "_t"], kind="stable")
    return pd.to_numeric(df["Patv"], errors="coerce").clip(lower=0).to_numpy(dtype=float)


def fit(turbine: int, path: Path) -> Dict[str, Any]:
    """``Pbar`` and ``a_k`` for k = 1..288, estimated on the training period of one turbine."""
    y = _series(path)
    pbar = float(np.nanmean(y))
    a: List[float] = []
    for k in range(1, MAX_LAG + 1):
        u, v = y[:-k], y[k:]
        ok = np.isfinite(u) & np.isfinite(v)
        if ok.sum() < 100:
            a.append(0.0)
            continue
        c = float(np.corrcoef(u[ok], v[ok])[0, 1])
        a.append(round(min(max(c, 0.0), 1.0), 6) if np.isfinite(c) else 0.0)
    return {"turbine": int(turbine), "file": path.name, "content_hash": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            "mean_kw": round(pbar, 3), "n_points": int(np.isfinite(y).sum()), "a_k": a}


def freeze(force: bool = False, log=print) -> Path:
    """Write ``data/reference/reference_model.json`` from the frozen training slices."""
    if REFERENCE_PATH.exists() and not force:
        raise FileExistsError(f"{REFERENCE_PATH} exists; pass --force to refit")
    files = sorted(GRU_DIR.glob("train_t*.csv"))
    if not files:
        raise FileNotFoundError("no data/gru/train_t*.csv; run `python run.py freeze-data` first")
    turbines = {}
    for p in files:
        t = int(p.stem.split("_t")[1])
        turbines[str(t)] = fit(t, p)
        e = turbines[str(t)]
        log(f"  turbine {t}: mean {e['mean_kw']:.1f} kW, a_1 {e['a_k'][0]:.3f}, a_18 {e['a_k'][17]:.3f}, a_288 {e['a_k'][-1]:.3f}")
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCE_PATH.write_text(json.dumps({
        "model": "Nielsen et al. new reference model, P(t+k|t) = a_k P(t) + (1 - a_k) Pbar",
        "protocol": "Madsen, Pinson, Kariniotakis, Nielsen, Nielsen, Wind Engineering 29(6):475-489, 2005, eq. (4)",
        "estimated_on": {"days": [1, TRAIN_LAST_DAY], "note": "the training period only; no target window is used"},
        "max_lag_steps": MAX_LAG, "rated_kw": RATED_KW, "turbines": turbines,
    }, indent=1), encoding="utf-8")
    log(f"wrote {REFERENCE_PATH.relative_to(PROJECT_ROOT)} for {len(turbines)} turbines")
    return REFERENCE_PATH


# ------------------------------------------------------------------ use


def parameters() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        if not REFERENCE_PATH.exists():
            raise FileNotFoundError(f"{REFERENCE_PATH} missing; run `python run.py freeze-reference`")
        _CACHE = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    return _CACHE


def parameters_hash() -> Optional[str]:
    return ("sha256:" + hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()[:16]) if REFERENCE_PATH.exists() else None


def new_reference_forecast(window: Any, horizon_h: int) -> List[float]:
    """``a_k P(t) + (1 - a_k) Pbar`` over the horizon, from the last measured power of the window."""
    p = parameters()["turbines"].get(str(window.turbine))
    if p is None:
        raise KeyError(f"turbine {window.turbine} is not in {REFERENCE_PATH.name}")
    last = pd.to_numeric(window.history(days=1)["Patv"], errors="coerce").clip(lower=0).ffill().bfill().fillna(0.0).to_numpy(dtype=float)
    p_t = float(last[-1])
    pbar, a = float(p["mean_kw"]), p["a_k"]
    n = int(horizon_h) * STEPS_PER_HOUR
    return [round(float(a[k] * p_t + (1.0 - a[k]) * pbar), 1) for k in range(n)]
