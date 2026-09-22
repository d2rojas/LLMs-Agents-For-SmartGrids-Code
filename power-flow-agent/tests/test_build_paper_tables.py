"""Offline tests for benchmarks/build_paper_tables.py (no LLM, no network)."""

import copy
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks import build_paper_tables as bpt  # noqa: E402


def _report(rows_kwargs):
    row = {
        "model": "openrouter:openai/gpt-5.4",
        "method": "pfagent",
        "task": "pfagent",
        "case_name": "case14",
    }
    row.update(rows_kwargs)
    runs = [
        {"method": "pfagent", "case_name": "case14", "ok": True, "formulation_exact": True, "metrics": {"kcl_mean_mismatch_mw": 0.1}},
        {"method": "pfagent", "case_name": "case14", "ok": True, "formulation_exact": True, "metrics": {"kcl_mean_mismatch_mw": 0.3}},
        {"method": "pfagent", "case_name": "case14", "ok": True, "formulation_exact": False, "metrics": {"kcl_mean_mismatch_mw": 99.0}},
        {"method": "pfagent", "case_name": "case14", "ok": False, "formulation_exact": True, "metrics": {"kcl_mean_mismatch_mw": 99.0}},
        {"method": "pfagent", "case_name": "case14", "ok": True, "formulation_exact": None, "metrics": {"kcl_mean_mismatch_mw": 0.5}},
    ]
    return {"runs": runs, "scoreboard": [copy.deepcopy(row)], "scoreboard_per_case": [copy.deepcopy(row)]}


def test_backfill_kcl_solved_matches_evaluate_llms_formula_when_missing():
    """2026-09-22, editor finding: GPT-5.4's frozen reports lack
    kcl_mean_mismatch_mw_formulation_exact_mean (added to evaluate_llms.py's live
    aggregate after GPT-5.4 was last rescored), so every GPT-5.4 row printed "--" for
    "B_mean solved" while gpt-4o-mini/sol printed a real number for the identical
    computation. The backfill must reproduce evaluate_llms.py's own formula exactly:
    ok rows where formulation_exact is not False (so None -- the LLM-only case --
    passes too), mean of metrics.kcl_mean_mismatch_mw. Expected here: items 1, 2, 5
    qualify (0.1, 0.3, 0.5); item 3 fails formulation_exact is False; item 4 fails ok.
    """
    data = _report({})
    bpt._backfill_kcl_solved(data)
    expected = (0.1 + 0.3 + 0.5) / 3
    assert abs(data["scoreboard"][0]["kcl_mean_mismatch_mw_formulation_exact_mean"] - expected) < 1e-12
    assert abs(data["scoreboard_per_case"][0]["kcl_mean_mismatch_mw_formulation_exact_mean"] - expected) < 1e-12


def test_backfill_kcl_solved_does_not_override_an_existing_value():
    """A row that already carries a real (non-null) value must be left alone -- this
    is a backfill for missing data, not a recompute of everything."""
    data = _report({"kcl_mean_mismatch_mw_formulation_exact_mean": 42.0})
    bpt._backfill_kcl_solved(data)
    assert data["scoreboard"][0]["kcl_mean_mismatch_mw_formulation_exact_mean"] == 42.0


def test_gpt54_validation_composite_no_longer_prints_a_dash_for_b_mean_solved():
    """End-to-end regression: build the real composite tables and confirm GPT-5.4's
    block prints a numeric (or literal 0) B_mean-solved cell on every row that has a
    B_mean-all value, matching gpt-4o-mini/sol's behavior for the same column."""
    import re
    import tempfile

    with tempfile.TemporaryDirectory(prefix="test_build_paper_tables_") as tmp:
        base = PROJECT_ROOT / "benchmarks"
        dirs = bpt._resolve_sources(Path(tmp), {"openrouter:openai/gpt-5.4": bpt.SOURCES["openrouter:openai/gpt-5.4"]}, base)
        assert dirs, "no GPT-5.4 sources resolved"
        for d in dirs:
            report = json.loads((Path(d) / "report.json").read_text(encoding="utf-8"))
            for row in report.get("scoreboard_per_case") or []:
                if row.get("kcl_mean_mismatch_mw_mean") is not None:
                    assert row.get("kcl_mean_mismatch_mw_formulation_exact_mean") is not None, (
                        f"{row.get('method')}: B_mean-all is present but B_mean-solved is still null after backfill"
                    )


def test_stress_sources_do_not_get_the_gpt54_backfill():
    """2026-09-22: the stress table's display is Daniela's call, pending -- an
    unrelated fix to the validation composite must not silently change it. Building
    from STRESS_SOURCES with the default (patch_gpt54=True) would still backfill,
    since GPT-5.4 stress rows have the same missing field; build_composite_tables
    explicitly passes patch_gpt54=False for stress_dirs, and this asserts that
    still holds by checking the actual call in the source."""
    import inspect

    src = inspect.getsource(bpt.build_composite_tables)
    assert "STRESS_SOURCES, base, patch_gpt54=False" in src, (
        "build_composite_tables must call _resolve_sources(..., STRESS_SOURCES, base, "
        "patch_gpt54=False) -- the GPT-5.4 B_mean-solved backfill must not reach the "
        "stress table until Daniela decides on its display"
    )
