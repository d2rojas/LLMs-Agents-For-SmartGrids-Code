"""The frozen data, the abnormal-data rules, the forecasters, the request generator and the scorer's arithmetic."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import HISTORY_DAYS, HORIZONS_H, STEPS_PER_DAY  # noqa: E402
from evaluation.requests import generate_requests, requests_digest, window_for  # noqa: E402
from evaluation.scoring import forecast_error  # noqa: E402
from methods.agent.gate import answer_matches, derive_answer  # noqa: E402
from solver import forecasters as F  # noqa: E402
from solver.data import BENCHMARK_DIR, abnormal_mask, content_hash, instances, load_manifest, load_window  # noqa: E402


def test_manifest_hashes_match_the_files():
    m = load_manifest()
    assert len(m["instances"]) == 20
    for e in m["instances"]:
        assert content_hash(BENCHMARK_DIR / e["file"]) == e["content_hash"], e["file"]
        assert e["record_count"] == (HISTORY_DAYS + 2) * STEPS_PER_DAY
        assert e["target_days"][0] > 214   # the KDD Cup test period; the GRU never saw it


def test_edited_file_is_refused(tmp_path, monkeypatch):
    m = load_manifest()
    e = m["instances"][0]
    bad = dict(e, content_hash="sha256:0000")
    m2 = dict(m, instances=[bad] + m["instances"][1:])
    with pytest.raises(ValueError):
        load_window(e["turbine"], e["base_day"], manifest=m2)


def test_abnormal_rules():
    df = pd.DataFrame({"Patv": [100, 0, -5, np.nan, 50, 60], "Wspd": [5, 5, 1, 5, 5, 5], "Pab1": [0, 0, 0, 0, 95, 0], "Pab2": [0] * 6, "Pab3": [0] * 6,
                       "Ndir": [0, 0, 0, 0, 0, 800], "Wdir": [0] * 6})
    m = abnormal_mask(df).tolist()
    assert m == [False, True, False, True, True, True]


def test_forecasters_have_the_right_length_and_range():
    w = load_window(8, 201)
    for h in HORIZONS_H:
        for fn in (F.persistence, F.power_curve_forecast, F.gru_forecast):
            s = fn(w, h)
            assert len(s) == h * 6 and all(0.0 <= v <= 1500.0 for v in s), fn.__name__
    curve = F.fit_power_curve(w)
    assert curve["bins"] and curve["max_median_kw"] > 500


def test_requests_are_stable_and_cover_the_matrix():
    a = generate_requests(seed=0)
    b = generate_requests(seed=0)
    assert len(a) == 20 * len(HORIZONS_H)
    assert requests_digest(a) == requests_digest(b)
    assert requests_digest(generate_requests(seed=1)) != requests_digest(a)
    assert {r.question for r in a} == {"peak_hour", "energy_kwh", "none"}
    for r in a[:6]:
        assert str(r.turbine) in r.text and str(r.history_days[1]) in r.text and f"{r.horizon_hours}" in r.text


def test_forecast_error_uses_only_scored_points():
    w = load_window(8, 201)
    t = w.target(3)
    series = [float(v) if np.isfinite(v) else 0.0 for v in np.clip(t["Patv"].to_numpy(dtype=float), 0, None)]
    e = forecast_error(series, w, 3)
    assert e["mae"] == 0.0 and e["rmse"] == 0.0 and e["n_scored"] == int((~t["abnormal"]).sum())
    assert forecast_error(series[:-1], w, 3)["mae"] is None


def test_answer_derivation():
    s = [0.0] * 6 + [100.0] * 6 + [50.0] * 6
    assert derive_answer("peak_hour", s) == 2.0
    assert derive_answer("energy_kwh", s) == 150.0
    assert derive_answer("none", s) is None
    assert answer_matches("peak_hour", 2, s) and not answer_matches("peak_hour", 3, s) and not answer_matches("peak_hour", 1, s)
    near = [100.0] * 6 + [99.0] * 6 + [50.0] * 6   # hours 1 and 2 within 2 %: both accepted
    assert answer_matches("peak_hour", 1, near) and answer_matches("peak_hour", 2, near) and not answer_matches("peak_hour", 3, near)
    assert answer_matches("energy_kwh", 151.0, s) and not answer_matches("energy_kwh", 170.0, s)
    assert answer_matches("none", None, s) is None
