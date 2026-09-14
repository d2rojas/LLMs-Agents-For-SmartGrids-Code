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
    "Structured", "Few-shot", "Chain-of-thought", "RAG",
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
        "voltage_mae_mean": v_mae,
        "flow_mae_mean": 0.1234,
        "converged_rate": 1.0,
        "faithful_numbers_mean": 0.9,
        "safe_failure_rate": 1.0,
        "safe_failure_total": 2,
        "claimed_success_on_failure_rate": 0.0,
        "claimed_success_on_failure_total": 2,
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
    assert rows[0][0] == r"\multirow{4}{*}{LLM-only (Sec.~\ref{sec:prompting})}"
    assert rows[4][0] == r"\multirow{4}{*}{Single-call (Sec.~\ref{sec:prompting})}"
    assert rows[8][0] == r"\multirow{5}{*}{Architectures (Sec.~\ref{sec:agents})}"
    assert rows[1][0] == "" and tex.splitlines()[1].startswith(" & Few-shot")
    # no tabular preamble or rules other than \midrule
    assert r"\begin{tabular}" not in tex and r"\toprule" not in tex and r"\bottomrule" not in tex


def test_missing_methods_are_dashes(reports_dir, tmp_path):
    _, tex = _run(reports_dir, tmp_path)
    by_label = {}
    for i, r in enumerate(_data_rows(tex)):
        by_label.setdefault((i // 4 if i < 8 else 2, r[1]), r[2:])
    llm_only_structured = _data_rows(tex)[0][2:]
    expected = [MISSING] * len(COLUMNS)
    expected[[c.name for c in COLUMNS].index("Calls")] = "n/a"  # LLM-only has no tools
    assert llm_only_structured == expected
    for label in ("ReAct", "Plan-and-Act", "PFAgent: ReAct + gate"):
        assert by_label[(2, label)] == [MISSING] * len(COLUMNS)


def test_number_formatting_and_weighting(reports_dir, tmp_path):
    _, tex = _run(reports_dir, tmp_path)
    rows = _data_rows(tex)
    structured = rows[4]
    assert structured[1] == "Structured"
    solved, form, v_mae, f_mae, fr, faith, sfr, claim, calls, tok, ttv = structured[2:]
    assert solved == "83.3"  # item-weighted, not 75.0
    assert form == "70.0"  # (0.8*40 + 0.5*20) / 60
    # V_MAE weighted by solved items: (1e-5*40 + 4e-5*10) / 50 = 1.6e-5
    assert v_mae == r"$1.60{\times}10^{-5}$"
    assert f_mae == "0.12"
    assert fr == "100.0" and faith == "90.0" and sfr == "100.0" and claim == "0.0"
    assert calls == "1.3"  # (1*40 + 2*20) / 60
    assert tok == "1100"  # (1000*40 + 1300*20) / 60
    assert ttv == "2.7"
    rule = rows[8]
    assert rule[1] == "Rule-based parser, no LLM"
    assert rule[2 + 2] == "0"  # V_MAE exactly zero
    assert rule[2 + 9] == "n/a"  # no LLM, so tokens are not applicable
    assert rule[2 + 10] == "0.1"


def test_best_prompt_selection(reports_dir, tmp_path):
    _, tex = _run(reports_dir, tmp_path)
    rows = _data_rows(tex)
    cot = rows[6]
    best = rows[9]
    assert cot[1] == "Chain-of-thought" and best[1] == "Single-call, best prompt"
    assert best[2:] == cot[2:]
    assert best[2 + 2] == r"$1.65{\times}10^{-5}$"
    assert best[2 + 1] == "92.5"


def test_per_system_and_scaling_csv(reports_dir, tmp_path):
    csv_path = tmp_path / "scaling.csv"
    out, _ = _run(reports_dir, tmp_path, "--per-system", "--scaling-csv", str(csv_path))
    for case in ("case14", "case30"):
        p = out.with_name(f"rows_{case}.tex")
        assert p.exists()
        rows = _data_rows(p.read_text(encoding="utf-8"))
        assert [r[1] for r in rows] == EXPECTED_LABELS
    case14 = _data_rows(out.with_name("rows_case14.tex").read_text(encoding="utf-8"))
    assert case14[4][2] == "100.0"  # structured, case14 only
    with csv_path.open(newline="") as fh:
        recs = list(csv.DictReader(fh))
    assert {(r["method"], r["case"]) for r in recs} == {
        (m, c) for m in ("single_call:structured", "single_call:cot", "rule_based") for c in ("case14", "case30")
    }
    rec = next(r for r in recs if r["method"] == "single_call:cot" and r["case"] == "case30")
    assert rec["n_buses"] == "30" and float(rec["formulation_exact_rate"]) == 0.90 and float(rec["n_tool_calls_mean"]) == 1.5


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
    assert _data_rows(out.read_text(encoding="utf-8"))[0][2] == "25.0"  # Solved from solved_rate
    assert main([str(d), "--out", str(out), "--no-prefer-rescored"]) == 0
    assert _data_rows(out.read_text(encoding="utf-8"))[0][2] == "100.0"  # fallback: success_rate
    # a null solved_rate (report written without per-item solved) also falls back
    null_rows = [_case_row(MODEL, "llm_only:structured", "case14", 40, 0.9, 0.0, None, 0.0, 3000, 4.0, solved_rate=None)]
    (d / "report.rescored.json").write_text(json.dumps(_report(null_rows, ["case14"])), encoding="utf-8")
    assert main([str(d), "--out", str(out)]) == 0
    assert _data_rows(out.read_text(encoding="utf-8"))[0][2] == "90.0"
