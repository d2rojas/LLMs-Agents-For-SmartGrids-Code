"""A narrowed N-1 scan (max_candidates below the branch count) is a formulation error, not benign."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks import metrics as bm  # noqa: E402

INTENDED = [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_n1_contingency", "args": {}}]


def _check(executed):
    return bm.formulation_check(INTENDED, executed)


def test_full_scan_is_exact() -> None:
    for args in ({}, {"max_candidates": 0}, {"top_k": 1}, {"max_candidates": 20}, {"max_candidates": 100}):
        fm = _check([{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_n1_contingency", "args": args}])
        assert fm["formulation_exact"] is True, (args, fm)


def test_narrowed_scan_changes_the_result() -> None:
    for v in (1, 3, 19):
        fm = _check([{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_n1_contingency", "args": {"top_k": 1, "max_candidates": v}}])
        assert fm["formulation_exact"] is False and fm["formulation_error_type"] == "extra_arg_changes_result", (v, fm)
        assert "scans only" in fm["detail"]


def test_threshold_follows_the_case() -> None:
    intended = [{"tool": "load_case", "args": {"case_name": "case30"}}, {"tool": "run_n1_contingency", "args": {}}]
    ok = bm.formulation_check(intended, [{"tool": "load_case", "args": {"case_name": "case30"}}, {"tool": "run_n1_contingency", "args": {"max_candidates": 41}}])
    bad = bm.formulation_check(intended, [{"tool": "load_case", "args": {"case_name": "case30"}}, {"tool": "run_n1_contingency", "args": {"max_candidates": 25}}])
    assert ok["formulation_exact"] is True and bad["formulation_exact"] is False


def test_v6_flags_an_unrequested_max_candidates() -> None:
    trace = {"rounds": [{"round": 1, "tools": [
        {"name": "load_case", "arguments": {"case_name": "case14"}, "output": "{}"},
        {"name": "run_n1_contingency", "arguments": {"top_k": 1, "criteria": "max_violations", "max_candidates": 3}, "output": "{}"}]}]}
    v6 = bm.argument_grounding_check(trace, "Load case14 and run an N-1 contingency analysis and report the worst single outage.")
    assert v6["passed"] is False and any(a["arg"] == "max_candidates" for a in v6["invented_args"])
    ok = bm.argument_grounding_check({"rounds": [{"round": 1, "tools": [{"name": "run_n1_contingency", "arguments": {"top_k": 3}, "output": "{}"}]}]}, "report the 3 worst outages")
    assert ok["passed"] is True
    stated = bm.argument_grounding_check(trace, "scan only 3 candidate branches and report the worst outage")
    assert stated["passed"] is True
