"""Offline tests for benchmarks/build_split_tool_appendix.py (no LLM, no network)."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks import build_paper_tables as bpt  # noqa: E402
from benchmarks import build_split_tool_appendix as bsta  # noqa: E402


def test_every_split_tool_source_dir_has_a_rescored_report():
    """Every before/after directory SPLIT_TOOL_SOURCES points at must carry a
    report.rescored.json -- a stale/unrescored source here would silently print the
    pre-fix Solved definition one appendix table away from the main body (Table 6),
    which is exactly the mismatch the editor found between load_split and the launch."""
    checked = 0
    for model, methods in bpt.SPLIT_TOOL_SOURCES.items():
        for method, paths in methods.items():
            for side in ("before", "after"):
                d = PROJECT_ROOT / "benchmarks" / paths[side]
                assert (d / "report.rescored.json").is_file(), f"{model}/{method}/{side}: {d} has no report.rescored.json"
                checked += 1
    assert checked >= 10


def test_split_tool_appendix_rows_sum_to_100():
    """Every before/after cell group (Solved + Escalated + Wrong-unflagged, using the
    full aggregate even though only Form./Solved/Wrong-unflagged are printed) sums to
    100% within rounding, for every model/method/side SPLIT_TOOL_SOURCES declares.

    2026-09-22: this check alone did NOT catch the editor's before-side bug (gpt-4o-mini
    and sol PFAgent before printing Wrong-unflagged=0.0 instead of 27.5/37.5) because the
    wrong (v6v7) triple is ALSO internally self-consistent -- it sums to 100% against
    solved_rate on its own, just describing a different, counterfactual gated re-scoring
    instead of the plain as-run one. A sums check can never distinguish "the right triple"
    from "a different but still-consistent triple"; see
    test_before_side_reads_plain_fields_even_when_v6v7_present for the check that does."""
    checked = 0
    for model, methods in bpt.SPLIT_TOOL_SOURCES.items():
        for method, paths in methods.items():
            for side in ("before", "after"):
                agg = bsta._aggregate(model, method, paths[side], side)
                assert agg is not None, f"{model}/{method}/{side}: no aggregate (source missing or empty)"
                bsta._check_sums(f"{model}/{method}/{side}", agg)  # raises SystemExit if not ~1.0
                checked += 1
    assert checked >= 10


def test_before_side_reads_plain_fields_even_when_v6v7_present():
    """Regression for the editor's finding: results_validation_gpt-4o-mini_agents and
    results_validation_sol_n40_clean/pfagent/case14 (both PFAgent "before" sources) carry
    an offline escalated_rate_v6v7/wrong_silently_rate_v6v7 pair from a later, interim
    rescore pass, alongside the plain escalated_rate/wrong_silently_rate the run actually
    produced under V1-V5. fill_table.COLUMNS prefers the v6v7 key when present (correct
    for a live/"after" row), which silently turned both these "before" rows' real
    Wrong-unflagged (27.5 and 37.5) into 0.0 -- erasing the largest effect in the table
    and making the redesign look like it changed nothing. A "before" aggregate must
    always equal what the plain fields say, never the v6v7 ones, whenever both are
    present on the same source."""
    import json

    cases = [
        ("openrouter:openai/gpt-4o-mini", "pfagent", "results_validation_gpt-4o-mini_agents", 0.275),
        ("openrouter:openai/gpt-5.6-sol", "pfagent", "results_validation_sol_n40_clean/pfagent/case14", 0.375),
    ]
    checked = 0
    for model, method, rel, expected_wrong in cases:
        raw = json.loads((PROJECT_ROOT / "benchmarks" / rel / "report.rescored.json").read_text(encoding="utf-8"))
        rows = [r for r in (raw.get("scoreboard_per_case") or raw.get("scoreboard") or []) if (r.get("method") or r.get("task")) == method]
        assert rows, f"{rel}: no {method} row in the raw report"
        row = rows[0]
        assert row.get("wrong_silently_rate_v6v7") is not None, f"{rel}: fixture assumption broken -- no v6v7 field present to guard against"
        assert row.get("wrong_silently_rate_v6v7") != row.get("wrong_silently_rate"), f"{rel}: plain and v6v7 happen to agree -- this case no longer exercises the bug"

        agg = bsta._aggregate(model, method, rel, "before")
        assert agg is not None
        assert abs((agg.get("Wrong-unflagged") or 0.0) - expected_wrong) < 1e-9, (
            f"{model}/{method} before: Wrong-unflagged={agg.get('Wrong-unflagged')}, expected the plain "
            f"rate {expected_wrong}, not the v6v7 one ({row.get('wrong_silently_rate_v6v7')})"
        )
        checked += 1
    assert checked == len(cases)


def test_gpt4o_mini_and_sol_after_side_points_at_the_launch_not_load_split():
    """Regression for the editor's finding: load_split's gpt-4o-mini PFAgent (97.5
    formulation, 27 solved) disagrees with the launch's (100.0, 28), and the main
    table body (SOURCES) is built from the launch -- so this appendix's "after" must
    match SOURCES' own directory for the same model/method, never load_split, or the
    appendix prints a different number than Table 6 for the same cell."""
    for model in ("openrouter:openai/gpt-4o-mini", "openrouter:openai/gpt-5.6-sol"):
        for method in ("pfagent", "react_nogate"):
            after = bpt.SPLIT_TOOL_SOURCES[model][method]["after"]
            assert "results_validation_load_split" not in after, f"{model}/{method}: after={after} should be the launch, not load_split"
            assert after == bpt.SOURCES[model][method], f"{model}/{method}: appendix after={after} must match the main table's own source {bpt.SOURCES[model][method]}"


def test_gpt54_after_side_stays_load_split():
    """GPT-5.4 has no split-tool launch directory -- its "after" is, and must stay,
    results_validation_load_split, the only split-tool run it has."""
    for method in ("pfagent", "react_nogate"):
        after = bpt.SPLIT_TOOL_SOURCES["openrouter:openai/gpt-5.4"][method]["after"]
        assert "results_validation_load_split/gpt-5.4" in after
