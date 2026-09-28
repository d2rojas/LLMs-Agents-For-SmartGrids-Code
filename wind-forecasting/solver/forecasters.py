"""The trusted forecasters: three deterministic ways of writing the next 48 hours from the history alone.

None of them sees anything after the last history day. They are what the tools of
``solver/tools.py`` call, what the rule-based row uses directly, and what the
gated agent's answer must trace to.

    persistence     the last full day of power, repeated
    power_curve     the wind-to-power curve fitted on the 14 days, applied to the last day's wind, repeated
    gru             the GRU of ``solver/gru.py``, trained here on this farm's training period
    foundation      the pretrained foundation model of ``solver/foundation.py``, never trained here
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config import ABNORMAL_WSPD, STEPS_PER_DAY, STEPS_PER_HOUR
from solver.data import Window

BIN_EDGES = [round(x * 0.5, 1) for x in range(0, 51)]   # 0 .. 25 m/s in 0.5 m/s steps


def _last_day(window: Window) -> pd.DataFrame:
    return window.history(days=1)


def persistence(window: Window, horizon_h: int) -> List[float]:
    """The last history day's power, repeated over the horizon; missing values as 0."""
    last = pd.to_numeric(_last_day(window)["Patv"], errors="coerce").clip(lower=0).fillna(0.0).to_numpy(dtype=float)
    if len(last) < STEPS_PER_DAY:
        raise ValueError(f"the last history day has {len(last)} rows, not {STEPS_PER_DAY}")
    n = int(horizon_h) * STEPS_PER_HOUR
    reps = int(np.ceil(n / len(last)))
    return [round(float(v), 1) for v in np.tile(last, reps)[:n]]


def fit_power_curve(window: Window) -> Dict[str, Any]:
    """Median power per 0.5 m/s wind bin over the 14 history days, abnormal rows excluded."""
    h = window.frame[window.frame["Day"] <= window.history_end_day]
    h = h[~h["abnormal"]]
    w = pd.to_numeric(h["Wspd"], errors="coerce")
    p = pd.to_numeric(h["Patv"], errors="coerce").clip(lower=0)
    ok = w.notna() & p.notna()
    w, p = w[ok], p[ok]
    b = pd.cut(w, BIN_EDGES, labels=False, include_lowest=True)
    med = p.groupby(b).median()
    cnt = p.groupby(b).size()
    curve = []
    for i in range(len(BIN_EDGES) - 1):
        if i in med.index and cnt[i] >= 3:
            curve.append({"wspd_from": BIN_EDGES[i], "wspd_to": BIN_EDGES[i + 1], "median_kw": round(float(med[i]), 1), "n": int(cnt[i])})
    rated = max((c["median_kw"] for c in curve), default=window.rating_kw)
    cut_in = next((c["wspd_from"] for c in curve if c["median_kw"] > 0.02 * window.rating_kw), None)
    return {"bins": curve, "n_points": int(ok.sum()), "cut_in_ms": cut_in, "max_median_kw": round(float(rated), 1), "rated_kw": window.rating_kw}


def apply_power_curve(curve: Dict[str, Any], wind_ms: np.ndarray, rating_kw: Optional[float] = None) -> np.ndarray:
    bins = curve["bins"]
    if not bins:
        return np.zeros(len(wind_ms))
    xs = np.array([(b["wspd_from"] + b["wspd_to"]) / 2 for b in bins])
    ys = np.array([b["median_kw"] for b in bins])
    w = np.nan_to_num(wind_ms.astype(float), nan=0.0)
    out = np.interp(w, xs, ys, left=0.0, right=ys[-1])
    out[w < ABNORMAL_WSPD] = np.minimum(out[w < ABNORMAL_WSPD], ys[0] if len(ys) else 0.0)
    return np.clip(out, 0.0, rating_kw if rating_kw is not None else float(curve.get("rated_kw", max(ys))))


def power_curve_forecast(window: Window, horizon_h: int, curve: Optional[Dict[str, Any]] = None) -> List[float]:
    """The fitted curve applied to the last day's wind speeds, repeated over the horizon."""
    curve = curve or fit_power_curve(window)
    wind = pd.to_numeric(_last_day(window)["Wspd"], errors="coerce").ffill().bfill().fillna(0.0).to_numpy(dtype=float)
    if len(wind) < STEPS_PER_DAY:
        raise ValueError(f"the last history day has {len(wind)} rows, not {STEPS_PER_DAY}")
    n = int(horizon_h) * STEPS_PER_HOUR
    reps = int(np.ceil(n / len(wind)))
    return [round(float(v), 1) for v in apply_power_curve(curve, np.tile(wind, reps)[:n], window.rating_kw)]


def gru_forecast(window: Window, horizon_h: int) -> List[float]:
    from solver import gru

    return gru.forecast(window, horizon_h)


def foundation_forecast(window: Window, horizon_h: int) -> List[float]:
    from solver import foundation

    return foundation.forecast(window, horizon_h)


def history_summary(window: Window) -> Dict[str, Any]:
    """What a forecaster would want to know before choosing: per-day means, the last values, data quality."""
    h = window.frame[window.frame["Day"] <= window.history_end_day]
    days = []
    for d, g in h.groupby("Day"):
        p = pd.to_numeric(g["Patv"], errors="coerce").clip(lower=0)
        w = pd.to_numeric(g["Wspd"], errors="coerce")
        days.append({"day": int(d), "rows": int(len(g)), "rows_with_data": int((g["Patv"].notna() & g["Wspd"].notna()).sum()),
                     "rows_turbine_stopped_or_curtailed": int(g["abnormal"].sum()),
                     "mean_kw": None if p.isna().all() else round(float(p.mean()), 1), "max_kw": None if p.isna().all() else round(float(p.max()), 1),
                     "mean_wspd": None if w.isna().all() else round(float(w.mean()), 2)})
    last = h.tail(6)
    return {
        "turbine": window.turbine, "history_days": [window.base_day, window.history_end_day], "rows": int(len(h)),
        "sampling_minutes": 10, "rated_kw": window.rating_kw, "per_day": days,
        "last_hour": [{"day": int(r.Day), "time": str(r.Tmstamp), "wspd": None if pd.isna(r.Wspd) else round(float(r.Wspd), 2),
                       "patv_kw": None if pd.isna(r.Patv) else round(max(float(r.Patv), 0.0), 1)} for r in last.itertuples()],
        "last_day_complete": bool(days and days[-1]["rows_with_data"] >= 0.5 * STEPS_PER_DAY),
        "note": "rows_with_data counts rows with a wind speed and a power reading; a stopped or curtailed turbine is still data. Only a day with fewer than 72 such rows prevents a forecast.",
    }
