"""Offline tests for benchmarks/experiment_report.py on a tiny synthetic results tree."""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks import experiment_report as er  # noqa: E402
from llm.prompts import SYSTEM_PROMPT_EN  # noqa: E402

MODEL = "fake:scripted"
REQUEST = "Load case14 and run the power flow, then report the bus with the lowest voltage magnitude."
INTENDED = [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}]


def _row(method, request_id, *, solved, formulation_exact, error=None, raw="", **extra):
    row = {
        "model": MODEL,
        "provider": "fake",
        "task": method,
        "method": method,
        "case_name": "case14",
        "run": 0,
        "k": 1,
        "seed": 1813382119,
        "gen_seed": 0,
        "request_id": request_id,
        "difficulty": "plain",
        "request_text": REQUEST,
        "ok": error is None,
        "error": error,
        "cost_usd": 0.001,
        "metrics": {"voltage_mae": 1.2e-5 if solved else None, "flow_mae": 0.01 if solved else None},
        "raw_response": raw,
        "intended_calls": INTENDED,
        "executed_calls": INTENDED if formulation_exact else None,
        "formulation_exact": formulation_exact,
        "formulation_error_type": "ok" if formulation_exact else ("missed_step" if formulation_exact is False else None),
        "faithful_numbers": 1.0 if solved else 0.0,
        "expected_outcome": "converged",
        "truth_converged": True,
        "solved": solved,
        "solved_reason": "numeric_ok" if solved else "voltage_error",
        "is_failure": False,
        "safe_failure": None,
        "claimed_success_on_failure": None,
        "abstained": False,
        "abstained_on_solvable": False,
        "has_mutation": False,
        "stale_state": None,
        "n_llm_calls": 1,
        "n_tool_calls": 2 if formulation_exact else 0,
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "wall_time_s": 1.5,
        "gate_checked": 1 if formulation_exact else 0,
        "gate_failed": 0,
        "gate_enforced": 0,
        "trace": {"architecture": method, "rounds": [], "status": "ok"},
    }
    row.update(extra)
    return row


def _per_case(method, n, solved_rate, form_rate, v_mae, calls):
    return {
        "model": MODEL,
        "task": method,
        "method": method,
        "case_name": "case14",
        "n_items": n,
        "success_rate": solved_rate,
        "solved_rate": solved_rate,
        "formulation_exact_rate": form_rate,
        "formulation_exact_total": n if form_rate is not None else 0,
        "voltage_mae_mean": v_mae,
        "flow_mae_mean": 0.01,
        "converged_rate": 1.0,
        "faithful_numbers_mean": 0.8,
        "safe_failure_rate": None,
        "claimed_success_on_failure_rate": 0.0,
        "abstained_on_solvable_rate": 0.5 if method.startswith("llm_only") else 0.0,
        "n_tool_calls_mean": calls,
        "total_tokens_mean": 120,
        "wall_time_s_mean": 1.5,
        "cost_usd_total": 0.002,
    }


FULL_TRACE = {
    "architecture": "react",
    "gate": True,
    "memory": True,
    "status": "ok",
    "final_text": "Bus 14 has the lowest voltage magnitude (1.0376 p.u.). Total load 248.5 MW.",
    "rounds": [
        {
            "round": 1,
            "llm": {"content": None, "tool_calls": [{"id": "c1", "name": "load_case", "arguments": "{\"case_name\":\"case14\"}"}]},
            "tools": [{"id": "c1", "name": "load_case", "arguments": {"case_name": "case14"}, "output": "{\"case_name\": \"case14\", \"n_buses\": 14}", "gate": None, "enforced": False}],
        },
        {
            "round": 2,
            "llm": {"content": "Running the power flow.", "tool_calls": [{"id": "c2", "name": "run_powerflow", "arguments": "{}"}]},
            "tools": [
                {
                    "id": "c2",
                    "name": "run_powerflow",
                    "arguments": {},
                    "output": "{\"converged\": true, \"total_load_mw\": 248.5, \"total_generation_mw\": 262.1, \"total_loss_mw\": 13.6}" + " ┌─┐" * 20,
                    "gate": {"passed": True, "reasons": [], "mismatch_mw": 0.0},
                    "enforced": False,
                }
            ],
        },
        {"round": 3, "llm": {"content": "Bus 14 has the lowest voltage magnitude (1.0376 p.u.). Total load 248.5 MW.", "tool_calls": []}},
    ],
    "n_llm_calls": 3,
    "n_tool_calls": 2,
    "gate_checked": 1,
    "gate_failed": 0,
    "gate_enforced": 0,
}


@pytest.fixture
def results_dir(tmp_path):
    root = tmp_path / "results_synth"
    rep_dir = root / "fake_scripted"
    rep_dir.mkdir(parents=True)
    rows = [
        _row("pfagent", "case14-plain-000-s0", solved=True, formulation_exact=True, raw=FULL_TRACE["final_text"]),
        _row("pfagent", "case14-plain-001-s0", solved=False, formulation_exact=False, raw="I could not run the tools."),
        _row("llm_only:structured", "case14-plain-000-s0", solved=False, formulation_exact=None, raw='{"converged": false, "bus_voltages": []}', abstained=True, abstained_on_solvable=True, solved_reason="convergence_mismatch"),
        _row("llm_only:structured", "case14-plain-001-s0", solved=False, formulation_exact=None, error="APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient credits'}}", solved_reason="run_failed"),
        # a second case so the multi-case aggregate table is exercised
        _row("pfagent", "case30-plain-000-s0", solved=True, formulation_exact=True, case_name="case30", raw="Bus 30 has the lowest voltage."),
    ]
    report = {
        "config": {
            "models": [MODEL],
            "methods": ["pfagent", "llm_only:structured"],
            "tasks": ["pfagent", "llm_only:structured"],
            "cases": ["case14", "case30"],
            "runs": 1,
            "k": 1,
            "seeds": [0],
            "max_rounds": 8,
            "requests": {"source": "generated", "n_per_case_seed": 2, "difficulties": None},
            "temperature": 0.0,
            "timeout_s": 90.0,
        },
        "scoreboard": [],
        "scoreboard_per_case": [
            _per_case("pfagent", 2, 0.5, 0.5, 1.2e-5, 2.0),
            _per_case("llm_only:structured", 2, 0.0, None, None, 0.0),
            {**_per_case("pfagent", 1, 1.0, 1.0, 2.0e-5, 2.0), "case_name": "case30"},
        ],
        "runs": rows,
    }
    (rep_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (rep_dir / "scoreboard.json").write_text("[]", encoding="utf-8")
    trace_dir = rep_dir / "traces" / "pfagent" / "case14"
    trace_dir.mkdir(parents=True)
    payload = {"method": "pfagent", "model": MODEL, "case_name": "case14", "request_id": "case14-plain-000-s0", "run": 0, "request_text": REQUEST, "intended_calls": INTENDED, "executed_calls": INTENDED, "answer": FULL_TRACE["final_text"], "trace": FULL_TRACE}
    (trace_dir / "case14-plain-000-s0_run0.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / "logs").mkdir()
    (root / "logs" / "fake_scripted.log").write_text("ok\n", encoding="utf-8")
    return root


def test_report_has_six_sections_in_order(results_dir):
    out = er.generate(results_dir, max_examples=3)
    text = out.read_text(encoding="utf-8")
    positions = [text.index(t) for t in er.SECTION_TITLES]
    assert positions == sorted(positions)
    assert len(er.SECTION_TITLES) == 6
    results = text[text.index(er.SECTION_TITLES[2]) : text.index(er.SECTION_TITLES[3])]
    assert "### Agregado por método" in results  # two cases -> weighted aggregate table
    assert "| pfagent | 2 casos | 3 |" in results
    assert "Todos los métodos que llegan al solver" in text


def test_prompt_section_contains_system_prompts(results_dir):
    text = er.generate(results_dir).read_text(encoding="utf-8")
    prompts = text[text.index(er.SECTION_TITLES[1]) : text.index(er.SECTION_TITLES[2])]
    # engine method: the English system prompt verbatim (first line)
    assert SYSTEM_PROMPT_EN.splitlines()[0] in prompts
    # LLM-only method: rebuilt with build_messages on the perturbed case, tables truncated
    assert "## System Data" in prompts
    assert "líneas omitidas" in prompts
    assert "caracteres" in prompts
    assert "strategy=structured, forced=False" in prompts


def test_example_trace_rendered_from_trace_file(results_dir):
    text = er.generate(results_dir).read_text(encoding="utf-8")
    examples = text[text.index(er.SECTION_TITLES[3]) : text.index(er.SECTION_TITLES[4])]
    assert "archivo de traza completo" in examples
    assert "tool: run_powerflow({})" in examples
    assert "gate: PASS" in examples
    assert "Bus 14 has the lowest voltage magnitude" in examples
    assert "solved=True (numeric_ok)" in examples
    # a failed-formulation example for pfagent and a flagged one for llm_only
    assert "formulación fallida" in examples
    assert "con bandera de fallo" in examples
    # box characters from tool output are replaced by ASCII
    assert "┌" not in examples and "+-+" in examples


def test_what_ran_and_readings_report_credit_errors(results_dir):
    text = er.generate(results_dir).read_text(encoding="utf-8")
    assert "APIStatusError 402" in text
    readings = text[text.index(er.SECTION_TITLES[4]) : text.index(er.SECTION_TITLES[5])]
    assert "1 items fallaron por crédito" in readings
    assert "de abstención en LLM-only" in readings
    assert "El gate verificó" in readings
    files = text[text.index(er.SECTION_TITLES[5]) :]
    assert "report.json" in files and "fake_scripted.log" in files


def test_pdf_skipped_gracefully_without_pandoc(results_dir, monkeypatch, capsys):
    monkeypatch.setattr(er.shutil, "which", lambda name: None)
    out = er.generate(results_dir, pdf=True)
    captured = capsys.readouterr().out
    assert "pdf omitido" in captured and "pandoc" in captured
    assert out.is_file() and not out.with_suffix(".pdf").exists()


def test_pdf_failure_does_not_raise(results_dir, monkeypatch):
    monkeypatch.setattr(er.shutil, "which", lambda name: "/usr/bin/pandoc")

    def boom(*a, **k):
        raise FileNotFoundError("tectonic")

    monkeypatch.setattr(er.subprocess, "run", boom)
    ok, msg = er.build_pdf(er.generate(results_dir))
    assert ok is False and "pandoc falló" in msg


def test_cli_and_max_examples(results_dir):
    out = results_dir / "custom.md"
    assert er.main([str(results_dir), "--out", str(out), "--max-examples", "1"]) == 0
    text = out.read_text(encoding="utf-8")
    examples = text[text.index(er.SECTION_TITLES[3]) : text.index(er.SECTION_TITLES[4])]
    assert examples.count("**Ejemplo:") == 2  # one per method


def test_helpers():
    assert er.classify_error("APIStatusError: Error code: 402 - {...}").startswith("APIStatusError 402")
    assert er.classify_error("RuntimeError: GroundTruthNotConverged") == "GroundTruthNotConverged"
    assert er.classify_error(None) is None
    assert er.ascii_boxes("┌──┐→") == "+--+->"
    text = "## System Data\n" + "\n".join(f"row {i}" for i in range(20)) + "\n\n## Task\nx"
    tr = er.truncate_case_tables(text, keep=12)
    assert "row 11" in tr and "row 12" not in tr and "8 líneas omitidas" in tr and "## Task" in tr
    assert er.fmt_sci(1.65e-5) == "1.65e-05" and er.fmt_pct(0.5) == "50.0"
