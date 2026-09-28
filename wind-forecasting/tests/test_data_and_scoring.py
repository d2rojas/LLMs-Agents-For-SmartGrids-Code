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


def test_protocol_reference_model_is_persistence_then_the_mean():
    """The ANEMOS reference: a_k P(t) + (1-a_k) Pbar, persistence at short lags, the mean at long ones."""
    from solver import reference as R
    from solver.data import load_window

    p = R.parameters()["turbines"]["8"]
    assert p["a_k"][0] > 0.9 and p["a_k"][17] < 0.8 and p["a_k"][-1] < 0.1
    w = load_window(8, 201)
    last = float(w.history(days=1)["Patv"].clip(lower=0).ffill().iloc[-1])
    s3 = R.new_reference_forecast(w, 3)
    s48 = R.new_reference_forecast(w, 48)
    assert len(s3) == 18 and len(s48) == 288
    assert abs(s3[0] - last) < 0.1 * max(last, 1.0)              # ten minutes ahead it is persistence
    assert abs(s48[-1] - p["mean_kw"]) < 0.05 * p["mean_kw"]     # two days ahead it is the training mean


def test_improvement_score_is_the_protocol_formula():
    from evaluation.scoring import improvement_pct

    assert improvement_pct(50.0, 100.0) == 50.0     # half the reference's error
    assert improvement_pct(100.0, 100.0) == 0.0     # no better than the reference
    assert improvement_pct(150.0, 100.0) == -50.0   # worse
    assert improvement_pct(None, 100.0) is None and improvement_pct(10.0, 0.0) is None


def test_errors_are_normalised_by_installed_capacity():
    from config import RATED_KW
    from evaluation.scoring import forecast_error
    from solver.data import load_window

    w = load_window(8, 201)
    t = w.target(3)
    import numpy as np
    truth = np.clip(np.nan_to_num(t["Patv"].to_numpy(dtype=float)), 0, None)
    e = forecast_error([float(v) + 150.0 for v in truth], w, 3)   # 150 kW too high everywhere
    assert abs(e["mae"] - 150.0) < 1.0 and abs(e["bias"] + 150.0) < 1.0   # bias is measured minus predicted
    assert abs(100.0 * e["mae"] / RATED_KW - 10.0) < 0.1                  # 150 of 1500 kW is 10 %


def test_scaled_condition_keeps_the_ground_truth_exact():
    """The memorisation check: history and target move together, so the measurement stays real and exact."""
    from solver.data import load_window, scale_for

    a = load_window(8, 201)
    b = load_window(8, 201, condition="scaled")
    c = scale_for(8, 201)
    assert 0.82 <= c <= 1.18 and b.scale == c and a.scale == 1.0
    assert scale_for(8, 201) == c and scale_for(9, 201) != c        # drawn from the instance, never at run time
    assert abs(b.rating_kw - 1500.0 * c) < 0.2
    for h in (3, 48):
        ya = a.target(h)["Patv"].to_numpy(dtype=float)
        yb = b.target(h)["Patv"].to_numpy(dtype=float)
        import numpy as np
        assert np.allclose(np.nan_to_num(yb), np.nan_to_num(ya) * c, rtol=1e-6)   # the truth transformed, not noise
    assert b.frame["abnormal"].sum() == a.frame["abnormal"].sum()   # scaling changes no data-quality verdict


def test_a_forecaster_is_scale_free_but_a_memorised_series_is_not():
    """Every trusted forecaster follows the window's rating, so the scaled condition costs it nothing."""
    import numpy as np

    from solver import forecasters as F
    from solver import reference as R
    from solver.data import load_window

    a, b = load_window(9, 207), load_window(9, 207, condition="scaled")
    c = b.scale
    for fn in (F.persistence, F.power_curve_forecast, R.new_reference_forecast, F.gru_forecast):
        sa = np.asarray(fn(a, 3), dtype=float)
        sb = np.asarray(fn(b, 3), dtype=float)
        assert np.allclose(sb, sa * c, rtol=0.02, atol=1.0), fn.__name__
    # the error of a scale-free forecaster is the same share of its rating in both conditions
    from evaluation.scoring import forecast_error
    ea = forecast_error(F.gru_forecast(a, 3), a, 3)["mae"] / a.rating_kw
    eb = forecast_error(F.gru_forecast(b, 3), b, 3)["mae"] / b.rating_kw
    assert abs(ea - eb) < 0.01


def test_the_request_and_the_prompt_state_the_rating():
    from evaluation.requests import generate_requests, window_for
    from methods.common import Context, history_block
    from config import ModelSpec

    r = generate_requests(instance_ids=["t008-d201"], horizons=(3,), questions=("peak_hour",), condition="scaled")[0]
    w = window_for(r)
    assert r.condition == "scaled" and r.request_id.endswith("-scaled")
    assert f"{w.rating_kw:.0f} kW" in r.text
    ctx = Context(request_id=r.request_id, text=r.text, window=w, horizon_hours=3, spec=ModelSpec("none", "x"))
    assert f"rated {w.rating_kw:.0f} kW" in history_block(ctx)
