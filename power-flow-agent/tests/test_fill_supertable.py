"""Offline tests for benchmarks/fill_supertable.py on a tiny synthetic results directory."""

import csv
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.fill_supertable import COLUMN_NAMES, MISSING, NA, main  # noqa: E402

MODEL = "fake:scripted"
SYSTEMS = ["case14", "case30"]
METHODS = ["single_call:structured", "rule_based"]

EXPECTED_LABELS = [
    "Structured", "Few-shot", "Chain-of-thought", "RAG", "LLM only, forced",
    "Structured", "Few-shot", "Chain-of-thought", "RAG",
    "Rule-based parser, no LLM", "Single-call, best prompt", "ReAct", "Plan-and-Act", "PFAgent: ReAct + gate",
]


def _case_row(model, method, case, n_items, solved, form, calls, tokens, ttv):
    return {
        "model": model,
        "task": method,
        "method": method,
        "case_name": case,
        "n_items": n_items,
        "success_rate": 1.0,
        "solved_rate": solved,
        "formulation_exact_rate": form,
        "formulation_exact_total": n_items,
        "voltage_mae_mean": 1.65e-5,
        "flow_mae_mean": 0.1234,
        "convergence_match_rate": 1.0,
        "kcl_mean_mismatch_mw_mean": 0.0,
        "faithful_numbers_mean": 0.9,
        "faithful_answers_rate": 1.0,
        "faithful_answers_total": n_items,
        "stale_state_rate": 0.0,
        "stale_state_total": n_items,
        "safe_failure_rate": 1.0,
        "safe_failure_total": 2,
        "claimed_success_on_failure_rate": 0.0,
        "claimed_success_on_failure_total": 2,
        "escalated_rate": 0.05,
        "wrong_silently_rate": 0.15,
        "n_tool_calls_mean": calls,
        "total_tokens_mean": tokens,
        "wall_time_s_mean": ttv,
        "v_pass_rate": 1.0,
    }


def _report(rows, case):
    return {
        "config": {"models": sorted({r["model"] for r in rows}), "cases": [case], "methods": sorted({r["method"] for r in rows})},
        "scoreboard": [],
        "scoreboard_per_case": rows,
        "runs": [],
    }


# per (method, case): solved, form, calls, tokens
DATA = {
    ("single_call:structured", "case14"): (0.90, 0.85, 2.0, 10000),
    ("single_call:structured", "case30"): (0.70, 0.75, 1.5, 12000),
    ("rule_based", "case14"): (0.60, 0.60, 1.0, 0.0),
    ("rule_based", "case30"): (0.50, 0.55, 1.0, 0.0),
}


@pytest.fixture
def results_dir(tmp_path):
    """<method>/<case>/report.json like results_matrix_*; case14 of the LLM method also has a rescored sibling."""
    root = tmp_path / "results"
    for (method, case), (solved, form, calls, tokens) in DATA.items():
        model = "none:rule_based" if method == "rule_based" else MODEL
        d = root / method.replace(":", "_") / case
        d.mkdir(parents=True)
        (d / "report.json").write_text(json.dumps(_report([_case_row(model, method, case, 40, solved, form, calls, tokens, 3.0)], case)), encoding="utf-8")
    # rescored report: only it carries the final solved rate for single_call case14
    d = root / "single_call_structured" / "case14"
    orig = json.loads((d / "report.json").read_text(encoding="utf-8"))
    orig["scoreboard_per_case"][0]["solved_rate"] = 0.10
    (d / "report.json").write_text(json.dumps(orig), encoding="utf-8")
    resc = _report([_case_row(MODEL, "single_call:structured", "case14", 40, 0.90, 0.85, 2.0, 10000, 3.0)], "case14")
    (d / "report.rescored.json").write_text(json.dumps(resc), encoding="utf-8")
    return root


def _run(results_dir, tmp_path, *extra):
    out = tmp_path / "out.tex"
    assert main([str(results_dir), "--out", str(out), *extra]) == 0
    return out.read_text(encoding="utf-8")


def _data_rows(tex):
    """[cells] for every row ending in \\\\ that is not a header/multicolumn line."""
    rows = []
    for ln in tex.splitlines():
        if not ln.endswith(r"\\") or ln.startswith(r"\multicolumn") or ln.startswith("& &") or ln.startswith(r"\textbf{Setting}"):
            continue
        rows.append([c.strip() for c in ln[: -len(r"\\")].split(" & ")])
    return rows


def _block_headers(tex):
    return [ln for ln in tex.splitlines() if ln.startswith(r"\multicolumn{" + str(2 + len(COLUMN_NAMES)) + "}{l}")]


# ----------------------------------------------------------------------------- blocks layout


def test_blocks_headers_and_row_order(results_dir, tmp_path):
    tex = _run(results_dir, tmp_path)
    assert _block_headers(tex) == [
        r"\multicolumn{17}{l}{\textbf{IEEE 14-bus}} \\",
        r"\multicolumn{17}{l}{\textbf{IEEE 30-bus}} \\",
    ]
    lines = tex.splitlines()
    assert lines[0].startswith(r"\multicolumn{17}{l}{\textbf{IEEE 14-bus}}")
    # blocks separated by exactly one \midrule, placed right before the second header
    assert tex.count(r"\midrule") == 1
    assert lines[lines.index(_block_headers(tex)[1]) - 1] == r"\midrule"
    rows = _data_rows(tex)
    assert [r[1] for r in rows] == EXPECTED_LABELS + EXPECTED_LABELS
    assert all(len(r) == 2 + len(COLUMN_NAMES) for r in rows)
    for offset in (0, 14):
        assert rows[offset][0] == r"\multirow{5}{*}{LLM-only (Sec.~\ref{sec:prompting})}"
        assert rows[offset + 5][0] == r"\multirow{4}{*}{Single-call (Sec.~\ref{sec:prompting})}"
        assert rows[offset + 9][0] == r"\multirow{5}{*}{Architectures (Sec.~\ref{sec:agents})}"
        assert rows[offset + 1][0] == ""
    # rows only: no table/tabular wrapper
    assert r"\begin{table}" not in tex and r"\begin{tabular}" not in tex and r"\resizebox" not in tex


def test_blocks_values_na_and_missing(results_dir, tmp_path):
    tex = _run(results_dir, tmp_path)
    rows = _data_rows(tex)
    names = COLUMN_NAMES
    b14, b30 = rows[:14], rows[14:]
    # single_call:structured, per system, Solved from the rescored solved_rate (0.90, not 0.10)
    # order: Form., V_MAE, F_MAE, Solved, Solver status, B_mean, Faith. (per-answer), SFR,
    # Calls, Tok., Faith. (per-number), Stale, Escalated, Wrong (silent), Time (s)
    assert b14[5][1] == "Structured" and b14[5][2:] == [
        "85.0", r"$1.65{\times}10^{-5}$", "0.12", "90.0", "100.0", "0", "100.0", "100.0", "2.0", "10000", "90.0", "0.0",
        "5.0", "15.0", "3.00",
    ]
    assert b30[5][2] == "75.0" and b30[5][2 + 3] == "70.0" and b30[5][2 + names.index("Calls")] == "1.5" and b30[5][2 + names.index("Tok.")] == "12000"
    # best single-call prompt = the only one present, copied per system
    assert b14[10][1] == "Single-call, best prompt" and b14[10][2:] == b14[5][2:] and b30[10][2:] == b30[5][2:]
    # rule-based: Tok. is n/a, numbers per system
    assert b14[9][1] == "Rule-based parser, no LLM"
    assert b14[9][2 + names.index("Tok.")] == NA and b30[9][2 + names.index("Tok.")] == NA
    assert b14[9][2] == "60.0" and b30[9][2] == "55.0" and b30[9][2 + 3] == "50.0"
    # LLM-only rows are missing: all dashes except Calls = n/a
    expected_llm_only = [MISSING] * len(names)
    expected_llm_only[names.index("Calls")] = NA
    for block in (b14, b30):
        for i in range(5):
            assert block[i][2:] == expected_llm_only
        for i in (11, 12, 13):  # ReAct, Plan-and-Act, PFAgent absent
            assert block[i][2:] == [MISSING] * len(names)


def test_blocks_standalone_and_tabular_wrappers(results_dir, tmp_path):
    tex = _run(results_dir, tmp_path, "--standalone")
    assert tex.startswith(r"\begin{table}[!ht]") and tex.rstrip().endswith(r"\end{table}")
    assert r"\label{tab:pf_protocol_per_system}" in tex and r"\caption{" in tex
    assert r"\scriptsize" in tex and r"\resizebox{\textwidth}{!}{%" in tex
    assert r"\begin{tabular}{ll cccc cc cc cc cc cc c}" in tex and r"\toprule" in tex and r"\bottomrule" in tex
    assert r"\textbf{Setting} & \textbf{Method} & \textbf{Form.} & $V_{\mathrm{MAE}}$" in tex
    assert (
        r"\cmidrule(lr){3-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}\cmidrule(lr){11-12}"
        r"\cmidrule(lr){13-14}\cmidrule(lr){15-16}\cmidrule(lr){17-17}"
    ) in tex
    assert len(_block_headers(tex)) == 2 and [r[1] for r in _data_rows(tex)] == EXPECTED_LABELS * 2
    tab = _run(results_dir, tmp_path, "--wrap", "tabular")
    assert tab.startswith(r"\scriptsize") and r"\begin{table}" not in tab and r"\begin{tabular}" in tab


# ----------------------------------------------------------------------------- compact layout


def test_compact_layout(results_dir, tmp_path):
    tex = _run(results_dir, tmp_path, "--layout", "compact", "--standalone")
    assert r"\label{tab:pf_by_system}" in tex
    assert r"\begin{tabular}{ll cc cc}" in tex
    assert r"\scriptsize" in tex and r"\resizebox" not in tex  # narrow table, kept at natural width
    assert tex.rstrip().endswith("\\end{tabular}\n\\end{table}")
    assert r"\multicolumn{2}{c}{\textbf{Form. (\%)}} & \multicolumn{2}{c}{\textbf{Calls}}" in tex
    assert r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}" in tex
    assert r"\textbf{Setting} & \textbf{Method} & 14 & 30 & 14 & 30 \\" in tex
    rows = _data_rows(tex)
    assert [r[1] for r in rows] == EXPECTED_LABELS
    assert all(len(r) == 2 + 4 for r in rows)
    assert rows[0][0] == r"\multirow{5}{*}{LLM-only (Sec.~\ref{sec:prompting})}"
    assert rows[5][2:] == ["85.0", "75.0", "2.0", "1.5"]  # single_call:structured: Form. 14, 30; Calls 14, 30
    assert rows[10][2:] == rows[5][2:]  # best prompt
    assert rows[9][2:] == ["60.0", "55.0", "1.0", "1.0"]  # rule_based
    assert rows[0][2:] == [MISSING, MISSING, NA, NA]  # LLM-only missing, Calls n/a
    assert rows[13][2:] == [MISSING] * 4
    # one \midrule between each setting group (2) plus the header rule
    assert tex.count(r"\midrule") == 3
    rows_only = _run(results_dir, tmp_path, "--layout", "compact")
    assert r"\begin{tabular}" not in rows_only and rows_only.count(r"\midrule") == 2


# ----------------------------------------------------------------------------- csv / options


def test_csv_one_row_per_method_and_system(results_dir, tmp_path):
    csv_path = tmp_path / "per_system.csv"
    _run(results_dir, tmp_path, "--csv", str(csv_path))
    with csv_path.open(newline="") as fh:
        recs = list(csv.DictReader(fh))
    assert len(recs) == 14 * 2  # rows: unaffected by the new Hours column, still 14 method rows
    assert [(r["method"], r["case"]) for r in recs] == [(m, c) for m in EXPECTED_LABELS for c in SYSTEMS]
    assert set(recs[0].keys()) == {"setting", "method", "method_key", "case", "n_buses", "n_items", *COLUMN_NAMES}
    sc30 = next(r for r in recs if r["method"] == "Structured" and r["setting"] == "Single-call" and r["case"] == "case30")
    assert sc30["method_key"] == "single_call:structured" and sc30["n_buses"] == "30" and sc30["n_items"] == "40"
    assert float(sc30["Solved"]) == 0.70 and float(sc30["Form."]) == 0.75 and float(sc30["Calls"]) == 1.5
    rb14 = next(r for r in recs if r["setting"] == "Architectures" and r["method"].startswith("Rule-based") and r["case"] == "case14")
    assert rb14["Tok."] == NA and float(rb14["Solved"]) == 0.60
    llm14 = next(r for r in recs if r["setting"] == "LLM-only" and r["method"] == "RAG" and r["case"] == "case14")
    assert llm14["method_key"] == MISSING and llm14["Calls"] == NA and llm14["Solved"] == MISSING and llm14["n_items"] == "0"


def test_no_prefer_rescored_and_cases_filter(results_dir, tmp_path):
    tex = _run(results_dir, tmp_path, "--no-prefer-rescored")
    assert _data_rows(tex)[5][2 + 3] == "10.0"  # original report's solved_rate (Solved column)
    tex = _run(results_dir, tmp_path, "--cases", "case30")
    assert _block_headers(tex) == [r"\multicolumn{17}{l}{\textbf{IEEE 30-bus}} \\"]
    assert tex.count(r"\midrule") == 0 and len(_data_rows(tex)) == 14
    with pytest.raises(SystemExit):
        main([str(results_dir), "--out", str(tmp_path / "x.tex"), "--layout", "compact", "--metrics", "Bogus"])
