"""Offline tests for benchmarks/fill_table.py on a synthetic report.json."""

import csv
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.fill_table import (  # noqa: E402
    COLUMNS,
    MISSING,
    aggregate_all,
    best_single_call,
    fmt_int,
    fmt_pct,
    fmt_sci,
    main,
    table_blocks,
)

MODEL = "fake:scripted"

EXPECTED_LABELS = [
    "Structured", "Few-shot", "Chain-of-thought", "RAG", "LLM only, forced",
    "Structured", "Few-shot", "Chain-of-thought", "RAG",
    "Rule-based parser, no LLM", "Single-call, best prompt", "ReAct", "Plan-and-Act", "PFAgent: ReAct + gate",
]


def _case_row(model, method, case, n_items, success, form, v_mae, calls, tokens, ttv, **extra):
    row = {
        "model": model,
        "task": method,
        "method": method,
        "case_name": case,
        "n_items": n_items,
        "success_rate": success,
        "formulation_exact_rate": form,
        "formulation_exact_count": round(form * n_items),
        "formulation_exact_total": n_items,
        # The fixture does not distinguish "solved" from "all" -- both V_MAE and F_MAE
        # feed the same value into their formulation-exact-conditioned and unconditioned
        # fields, so a test asserting one implicitly asserts the other.
        "voltage_mae_mean": v_mae,
        "voltage_mae_formulation_exact_mean": v_mae,
        "flow_mae_mean": 0.1234,
        "flow_mae_formulation_exact_mean": 0.1234,
        "convergence_match_rate": 1.0,
        "kcl_mean_mismatch_mw_mean": 0.0,
        "kcl_mean_mismatch_mw_formulation_exact_mean": 0.0,
        "faithful_numbers_mean": 0.9,
        "safe_failure_rate": 1.0,
        "safe_failure_total": 2,
        "claimed_success_on_failure_rate": 0.0,
        "claimed_success_on_failure_total": 2,
        # Constant across every synthetic row on purpose: a weighted mean of a constant
        # is that constant regardless of the per-row item counts, so tests can assert on
        # it without redoing the weighting arithmetic.
        "escalated_rate": 0.0,
        "wrong_silently_rate": 0.1,
        "n_tool_calls_mean": calls,
        "total_tokens_mean": tokens,
        "wall_time_s_mean": ttv,
    }
    row.update(extra)
    return row


def _report(rows, cases):
    return {
        "config": {"models": sorted({r["model"] for r in rows}), "cases": cases, "methods": sorted({r["method"] for r in rows})},
        "scoreboard": [],
        "scoreboard_per_case": rows,
        "runs": [],
    }


@pytest.fixture
def reports_dir(tmp_path):
    """Two methods x two cases in one report, rule_based in a second one."""
    a = [
        # single_call:structured: success 1.0 (40 items) and 0.5 (20 items) -> weighted 83.3 %, unweighted 75 %
        _case_row(MODEL, "single_call:structured", "case14", 40, 1.0, 0.80, 1.0e-5, 1.0, 1000, 2.0),
        _case_row(MODEL, "single_call:structured", "case30", 20, 0.5, 0.50, 4.0e-5, 2.0, 1300, 4.0),
        # single_call:cot: higher formulation rate -> best prompt
        _case_row(MODEL, "single_call:cot", "case14", 40, 1.0, 0.95, 1.65e-5, 1.5, 2000, 3.0),
        _case_row(MODEL, "single_call:cot", "case30", 40, 1.0, 0.90, 1.65e-5, 1.5, 2000, 3.0),
    ]
    b = [
        _case_row("none:rule_based", "rule_based", "case14", 40, 0.6, 0.60, 0.0, 1.0, 0.0, 0.05),
        _case_row("none:rule_based", "rule_based", "case30", 40, 0.6, 0.60, 0.0, 1.0, 0.0, 0.05),
    ]
    d = tmp_path / "results"
    (d / "llm").mkdir(parents=True)
    (d / "rb").mkdir(parents=True)
    (d / "llm" / "report.json").write_text(json.dumps(_report(a, ["case14", "case30"])), encoding="utf-8")
    (d / "rb" / "report.json").write_text(json.dumps(_report(b, ["case14", "case30"])), encoding="utf-8")
    return d


def _run(reports_dir, tmp_path, *extra):
    out = tmp_path / "rows.tex"
    assert main([str(reports_dir), "--out", str(out), *extra]) == 0
    return out, out.read_text(encoding="utf-8")


def _data_rows(tex):
    rows = [ln for ln in tex.splitlines() if ln.endswith(r"\\")]
    parsed = []
    for ln in rows:
        cells = [c.strip() for c in ln[: -len(r"\\")].split(" & ")]
        parsed.append(cells)
    return parsed


def test_row_order_and_shape(reports_dir, tmp_path):
    _, tex = _run(reports_dir, tmp_path)
    rows = _data_rows(tex)
    assert [r[1] for r in rows] == EXPECTED_LABELS
    assert all(len(r) == 2 + len(COLUMNS) for r in rows)
    assert tex.count(r"\midrule") == 2
    assert rows[0][0] == r"\multirow{5}{*}{LLM-only (Sec.~\ref{sec:prompting})}"
    assert rows[5][0] == r"\multirow{4}{*}{Single-call (Sec.~\ref{sec:prompting})}"
    assert rows[9][0] == r"\multirow{5}{*}{Architectures (Sec.~\ref{sec:agents})}"
    assert rows[1][0] == "" and tex.splitlines()[1].startswith(" & Few-shot")
    # no tabular preamble or rules other than \midrule
    assert r"\begin{tabular}" not in tex and r"\toprule" not in tex and r"\bottomrule" not in tex


def test_missing_methods_are_dashes(reports_dir, tmp_path):
    _, tex = _run(reports_dir, tmp_path)
    data_rows = _data_rows(tex)
    block_sizes = [len(rows) for _setting, rows in table_blocks()]
    block_of = []
    for b, size in enumerate(block_sizes):
        block_of.extend([b] * size)
    by_label = {}
    for i, r in enumerate(data_rows):
        by_label.setdefault((block_of[i], r[1]), r[2:])
    llm_only_structured = _data_rows(tex)[0][2:]
    expected = [MISSING] * len(COLUMNS)
    assert llm_only_structured == expected
    for label in ("ReAct", "Plan-and-Act", "PFAgent: ReAct + gate"):
        assert by_label[(2, label)] == [MISSING] * len(COLUMNS)


def test_number_formatting_and_weighting(reports_dir, tmp_path):
    _, tex = _run(reports_dir, tmp_path)
    rows = _data_rows(tex)
    structured = rows[5]
    assert structured[1] == "Structured"
    form, v_mae_solved, v_mae_all, b_mean_solved, b_mean_all, solved, escalated, wrong_unflagged, traceable, tokens, time_s = structured[2:]
    assert form == "70.0"  # (0.8*40 + 0.5*20) / 60
    # V_MAE weighted by solved items: (1e-5*40 + 4e-5*10) / 50 = 1.6e-5 -- the fixture
    # feeds the same value into both the "solved" and "all" fields, so both columns
    # read the same number here.
    assert v_mae_solved == v_mae_all == r"$1.60{\times}10^{-5}$"
    assert b_mean_solved == b_mean_all == "0"  # kcl_mean_mismatch_mw is 0.0 in the fixture
    assert solved == "83.3"  # item-weighted, not 75.0
    assert escalated == "0.0" and wrong_unflagged == "10.0" and traceable == "90.0"
    assert tokens == "1100"  # (1000*40 + 1300*20) / 60
    assert time_s == "2.67"  # (2.0*40 + 4.0*20) / 60
    rule = rows[9]
    assert rule[1] == "Rule-based parser, no LLM"
    assert rule[2 + 1] == "0"  # V_MAE solved exactly zero
    assert rule[2 + 9] == "n/a"  # no LLM, so tokens are not applicable


def test_escalated_and_wrong_unflagged_columns_prefer_the_v6v7_gated_rate_when_present(tmp_path):
    """fill_table.py's Column keys-fallback: escalated_rate_v6v7 / wrong_silently_rate_v6v7
    (present only for a gated architecture -- see evaluate_llms._aggregate_group) take
    priority over the plain rate; a row without them (no gate) reads the plain rate."""
    gated = _case_row(MODEL, "pfagent", "case14", 40, 1.0, 1.0, 1e-5, 2.0, 5000, 4.0,
                       escalated_rate=0.05, wrong_silently_rate=0.15,
                       escalated_rate_v6v7=0.35, wrong_silently_rate_v6v7=0.0)
    ungated = _case_row(MODEL, "react_nogate", "case14", 40, 1.0, 1.0, 1e-5, 2.0, 5000, 4.0,
                         escalated_rate=0.0, wrong_silently_rate=0.275)
    d = tmp_path / "results"
    (d / "r").mkdir(parents=True)
    (d / "r" / "report.json").write_text(json.dumps(_report([gated, ungated], ["case14"])), encoding="utf-8")
    out = tmp_path / "rows.tex"
    assert main([str(d), "--out", str(out)]) == 0
    rows = _data_rows(out.read_text(encoding="utf-8"))
    pfagent_row = next(r for r in rows if r[1] == "PFAgent: ReAct + gate")
    react_row = next(r for r in rows if r[1] == "ReAct")
    assert pfagent_row[2 + 6] == "35.0" and pfagent_row[2 + 7] == "0.0"  # gated rate used
    assert react_row[2 + 6] == "0.0" and react_row[2 + 7] == "27.5"  # falls back to the plain rate


def test_best_prompt_selection(reports_dir, tmp_path):
    _, tex = _run(reports_dir, tmp_path)
    rows = _data_rows(tex)
    cot = rows[7]
    best = rows[10]
    assert cot[1] == "Chain-of-thought" and best[1] == "Single-call, best prompt"
    assert best[2:] == cot[2:]
    assert best[2 + 1] == r"$1.65{\times}10^{-5}$"  # V_MAE
    assert best[2 + 0] == "92.5"  # Form.


def test_per_system_and_scaling_csv(reports_dir, tmp_path):
    csv_path = tmp_path / "scaling.csv"
    out, _ = _run(reports_dir, tmp_path, "--per-system", "--scaling-csv", str(csv_path))
    for case in ("case14", "case30"):
        p = out.with_name(f"rows_{case}.tex")
        assert p.exists()
        rows = _data_rows(p.read_text(encoding="utf-8"))
        assert [r[1] for r in rows] == EXPECTED_LABELS
    case14 = _data_rows(out.with_name("rows_case14.tex").read_text(encoding="utf-8"))
    assert case14[5][2 + 5] == "100.0"  # Solved, structured, case14 only
    with csv_path.open(newline="") as fh:
        recs = list(csv.DictReader(fh))
    assert {(r["method"], r["case"]) for r in recs} == {
        (m, c) for m in ("single_call:structured", "single_call:cot", "rule_based") for c in ("case14", "case30")
    }
    rec = next(r for r in recs if r["method"] == "single_call:cot" and r["case"] == "case30")
    assert rec["n_buses"] == "30" and float(rec["formulation_exact_rate"]) == 0.90 and float(rec["n_tool_calls_mean"]) == 1.5


def test_duplicate_model_method_case_condition_raises(tmp_path):
    """Two reports for the same (model, method, case) with no condition tag (both default
    to "normal") is a merge hazard and must raise, not silently keep the latter."""
    from benchmarks.fill_table import DuplicateReportRowError, find_reports, load_case_rows

    row_a = _case_row(MODEL, "pfagent", "case14", 40, 1.0, 0.9, 1e-5, 2.0, 5000, 4.0)
    row_b = _case_row(MODEL, "pfagent", "case14", 5, 1.0, 0.9, 1e-5, 2.0, 5000, 4.0)
    d = tmp_path / "results"
    (d / "normal").mkdir(parents=True)
    (d / "also_normal").mkdir(parents=True)
    (d / "normal" / "report.json").write_text(json.dumps(_report([row_a], ["case14"])), encoding="utf-8")
    (d / "also_normal" / "report.json").write_text(json.dumps(_report([row_b], ["case14"])), encoding="utf-8")

    with pytest.raises(DuplicateReportRowError):
        load_case_rows(find_reports([str(d)]))


def test_same_method_case_different_condition_does_not_raise(tmp_path):
    """The same (model, method, case) under two different conditions (e.g. normal vs
    stress) is expected and must produce two distinct rows, not a collision."""
    from benchmarks.fill_table import find_reports, load_case_rows

    row_normal = _case_row(MODEL, "pfagent", "case14", 40, 1.0, 0.9, 1e-5, 2.0, 5000, 4.0)
    row_stress = _case_row(MODEL, "pfagent", "case14", 5, 0.2, 0.9, 1e-5, 2.0, 5000, 4.0)
    d = tmp_path / "results"
    (d / "normal").mkdir(parents=True)
    (d / "stress").mkdir(parents=True)
    normal_report = _report([row_normal], ["case14"])
    normal_report["config"]["condition"] = "normal"
    stress_report = _report([row_stress], ["case14"])
    stress_report["config"]["condition"] = "stress"
    (d / "normal" / "report.json").write_text(json.dumps(normal_report), encoding="utf-8")
    (d / "stress" / "report.json").write_text(json.dumps(stress_report), encoding="utf-8")

    rows = load_case_rows(find_reports([str(d)]))
    conditions = {r["condition"] for r in rows}
    assert conditions == {"normal", "stress"}
    assert len(rows) == 2


def test_gated_baselines_flag_changes_mapping():
    default = dict(table_blocks()[2][1])
    gated = dict(table_blocks(gated_baselines=True)[2][1])
    assert default["ReAct"] == "react_nogate" and default["Plan-and-Act"] == "plan_act_nogate"
    assert gated["ReAct"] == "react" and gated["Plan-and-Act"] == "plan_act"
    assert default["PFAgent: ReAct + gate"] == gated["PFAgent: ReAct + gate"] == "pfagent"


def test_formatters():
    assert fmt_sci(1.65e-5) == r"$1.65{\times}10^{-5}$"
    assert fmt_sci(9.996e-5) == r"$1.00{\times}10^{-4}$"
    assert fmt_sci(123.456) == r"$1.23{\times}10^{2}$"
    assert fmt_sci(0.0) == "0"
    assert fmt_sci(None) == MISSING and fmt_pct(None) == MISSING and fmt_int(float("nan")) == MISSING
    assert fmt_pct(0.8762) == "87.6"
    assert fmt_int(1099.6) == "1100"


def test_best_single_call_prefers_highest_formulation():
    agg = aggregate_all(
        [
            _case_row(MODEL, "single_call:rag", "case14", 10, 1.0, 0.7, 1e-5, 1, 1, 1),
            _case_row(MODEL, "single_call:few_shot", "case14", 10, 1.0, 0.7, 1e-5, 1, 1, 1),
        ]
    )
    assert best_single_call(agg) == "single_call:few_shot"  # tie -> skeleton order
    assert best_single_call({}) is None


# ----------------------------------------------------------------------------- rescored reports / Solved column


def test_solved_reads_solved_rate_and_prefers_rescored_report(tmp_path):
    from benchmarks.fill_table import find_reports

    # original: pre-scoring report (only success_rate); rescored sibling carries solved_rate
    orig = [_case_row(MODEL, "llm_only:structured", "case14", 40, 1.0, 0.0, None, 0.0, 3000, 4.0)]
    resc = [_case_row(MODEL, "llm_only:structured", "case14", 40, 1.0, 0.0, None, 0.0, 3000, 4.0, solved_rate=0.25, solved_count=10, solved_total=40)]
    d = tmp_path / "results" / "case14"
    d.mkdir(parents=True)
    (d / "report.json").write_text(json.dumps(_report(orig, ["case14"])), encoding="utf-8")
    (d / "report.rescored.json").write_text(json.dumps(_report(resc, ["case14"])), encoding="utf-8")

    assert find_reports([str(d)]) == [d / "report.rescored.json"]
    assert find_reports([str(d)], prefer_rescored=False) == [d / "report.json"]

    out = tmp_path / "rows.tex"
    assert main([str(d), "--out", str(out)]) == 0
    assert _data_rows(out.read_text(encoding="utf-8"))[0][2 + 5] == "25.0"  # Solved from solved_rate
    assert main([str(d), "--out", str(out), "--no-prefer-rescored"]) == 0
    assert _data_rows(out.read_text(encoding="utf-8"))[0][2 + 5] == "100.0"  # fallback: success_rate
    # a null solved_rate (report written without per-item solved) also falls back
    null_rows = [_case_row(MODEL, "llm_only:structured", "case14", 40, 0.9, 0.0, None, 0.0, 3000, 4.0, solved_rate=None)]
    (d / "report.rescored.json").write_text(json.dumps(_report(null_rows, ["case14"])), encoding="utf-8")
    assert main([str(d), "--out", str(out)]) == 0
    assert _data_rows(out.read_text(encoding="utf-8"))[0][2 + 5] == "90.0"
