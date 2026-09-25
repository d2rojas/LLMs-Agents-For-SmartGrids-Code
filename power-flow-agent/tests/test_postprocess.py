"""evaluation/postprocess.py on a synthetic run directory (no API keys, no solver)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.postprocess import aggregate, postprocess  # noqa: E402


def _row(rid: str, *, method="pfagent", model="openai:gpt-4o-mini", solved=True, escalated=False, wrong=False, exact=True, difficulty="plain"):
    return {
        "method": method, "task": method, "model": model, "case_name": "case14", "request_id": rid, "run": 0, "gen_seed": 0, "seed": 7,
        "difficulty": difficulty, "expected_outcome": "converged", "reference_solvable": True, "truth_converged": True,
        "request_text": f"Load case14 and run power flow ({rid}).",
        "intended_calls": [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}],
        "executed_calls": [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}] + ([] if exact else [{"tool": "get_status", "args": {}}]),
        "formulation_exact": exact, "formulation_error_type": "ok" if exact else "extra_step", "formulation_detail": "" if exact else "unintended tools: ['get_status']",
        "solved": solved, "solved_reason": "numeric_and_answer_ok" if solved else "formulation", "solved_autonomously": solved and not escalated,
        "escalated": escalated, "wrong_silently": wrong, "failure_detection_path": "text",
        "v_pass": True, "verification_outcome": "pass_first", "verification_attempts": 1,
        "faithful_answers": True, "faithful_numbers": 1.0, "n_numbers": 4, "n_untraceable_numbers": 0, "untraceable_numbers": [], "stale_state": False, "safe_failure": None,
        "metrics": {"voltage_mae": 0.0, "flow_mae": 0.0, "kcl_mean_mismatch_mw": 0.0, "power_balance_error": 1e-9},
        "n_llm_calls": 3, "n_tool_calls": 2, "n_tool_rounds": 2, "prompt_tokens": 5000, "completion_tokens": 300, "cost_usd": 0.001, "wall_time_s": 6.5,
        "system_prompt_hash": "2efb17dd2582", "error": None, "raw_response": None,
        "trace": {},
    }


def _trace(row):
    return {
        "method": row["method"], "model": row["model"], "case_name": "case14", "request_id": row["request_id"], "seed": 7, "run": 0,
        "difficulty": row["difficulty"], "request_text": row["request_text"], "intended_calls": row["intended_calls"], "executed_calls": row["executed_calls"],
        "answer": "Power flow converged. Total load 259.0 MW, total generation 272.4 MW, losses 13.4 MW, voltages 1.01 to 1.09 p.u.",
        "trace": {
            "architecture": "react", "gate": False, "final_gate": True, "memory": False, "max_rounds": 8, "status": "ok",
            "final_text": "Power flow converged.", "request_text": row["request_text"],
            "rounds": [
                {"round": 1, "llm": {"content": None, "tool_calls": [{"id": "c1", "name": "load_case", "arguments": "{\"case_name\": \"case14\"}"}], "usage": {"prompt_tokens": 900, "completion_tokens": 30}, "latency_s": 1.1},
                 "tools": [{"id": "c1", "name": "load_case", "arguments": {"case_name": "case14"}, "output": "{\"case_name\": \"case14\", \"n_buses\": 14, \"n_lines\": 20}", "gate": None, "enforced": False}]},
                {"round": 2, "llm": {"content": None, "tool_calls": [{"id": "c2", "name": "run_powerflow", "arguments": "{}"}], "usage": {"prompt_tokens": 1000, "completion_tokens": 20}, "latency_s": 1.0},
                 "tools": [{"id": "c2", "name": "run_powerflow", "arguments": {}, "output": "{\"converged\": true, \"total_load_mw\": 259.0, \"figure_json\": \"" + "x" * 3000 + "\"}", "gate": {"passed": True}, "enforced": False}]},
                {"round": 3, "final": True, "llm": {"content": "Power flow converged.", "tool_calls": [], "usage": {"prompt_tokens": 3100, "completion_tokens": 250}, "latency_s": 2.0}},
            ],
            "plan": None, "n_llm_calls": 3, "n_tool_calls": 2, "n_tool_rounds": 2, "prompt_tokens": 5000, "completion_tokens": 300, "wall_time_s": 6.5,
            "verification": [{"passed": True, "conditions": {"converged": {"passed": True, "residual": 0, "applicable": True, "label": "V1"}, "faithfulness": {"passed": True, "residual": 0.0, "label": "V4"}}}],
            "verification_attempts": 1, "verification_outcome": "pass_first", "verification_retry_messages": [],
        },
    }


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    d = tmp_path / "results" / "ieee14" / "2026-09-23" / "gpt-4o-mini" / "pfagent"
    raw = d / "raw"
    rows = [
        _row("case14-plain-001-s0"),
        _row("case14-plain-002-s0", solved=False, escalated=True, exact=False),
        _row("case14-multistep-003-s0", solved=False, wrong=True, difficulty="multistep"),
        _row("case14-multistep-004-s0", method="react_nogate", difficulty="multistep"),  # another method in the same report
    ]
    report = {
        "config": {"models": ["openai:gpt-4o-mini"], "methods": ["pfagent", "react_nogate"], "cases": ["case14"], "condition": "normal", "tool_variant": "load_split", "plan_variant": "text", "k": 1, "seeds": [0], "max_rounds": 8, "temperature": 0.0},
        "scoreboard": [{"model": "openai:gpt-4o-mini", "method": "pfagent", "task": "pfagent", "condition": "normal", "n_items": 3, "solved_autonomously_count": 1, "escalated_count": 1, "wrong_silently_count": 1, "formulation_exact_count": 2, "v_pass_count": 3, "faithful_answers_count": 3}],
        "runs": rows,
    }
    raw.mkdir(parents=True)
    (raw / "report.json").write_text(json.dumps(report), encoding="utf-8")
    for r in rows:
        p = raw / "traces" / r["method"] / "case14" / f"{r['request_id']}_run0.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_trace(r)), encoding="utf-8")
    (d / "config.json").write_text(json.dumps({"kind": "run", "date": "2026-09-23", "method": "pfagent", "method_runner_name": "pfagent", "model": "openai:gpt-4o-mini", "case": "case14", "condition": "normal", "tool_variant": "load_split"}), encoding="utf-8")
    return d


def test_postprocess_writes_every_artifact_and_filters_by_method(run_dir: Path) -> None:
    summary = postprocess(run_dir, quiet=True)
    agg = summary["aggregate"]
    assert agg["n"] == 3  # the react_nogate row is filtered out via config.json
    assert agg["solved_autonomously"] + agg["escalated"] + agg["wrong_unflagged"] + agg["run_errors"] + agg["other"] == agg["n"]
    assert (agg["solved_autonomously"], agg["escalated"], agg["wrong_unflagged"]) == (1, 1, 1)
    assert agg["formulation_exact"] == 2 and agg["formulation_errors"] == {"extra_step": 1}

    for name in ("REPORT.md", "summary.csv", "summary.json", "requests.jsonl"):
        assert (run_dir / name).is_file(), name
    traces = sorted(p.name for p in (run_dir / "traces").iterdir())
    assert len([t for t in traces if t.endswith(".transcript.txt")]) == 3
    assert len([t for t in traces if t.endswith(".narrative.txt")]) == 3
    assert len([t for t in traces if t.endswith(".json")]) == 3
    assert len([t for t in traces if t.endswith(".png")]) == 3
    assert (run_dir / "overview.png").is_file()
    assert traces[0].startswith("01_case14-multistep-003-s0")  # sorted by request id, numbered

    with (run_dir / "summary.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["outcome"] for r in rows] == ["wrong_unflagged", "solved", "escalated"]

    report = (run_dir / "REPORT.md").read_text(encoding="utf-8")
    assert "| Solved autonomously | 1 | 33.3% |" in report
    assert "## Wrong and unflagged (1)" in report and "case14-multistep-003-s0" in report
    assert "<-- differs" not in report  # agrees with the runner's scoreboard


def test_transcript_has_prompt_rounds_and_elided_figures(run_dir: Path) -> None:
    postprocess(run_dir, quiet=True)
    t = (run_dir / "traces" / "02_case14-plain-001-s0.transcript.txt").read_text(encoding="utf-8")
    assert "[system]   (hash 2efb17dd2582" in t
    assert "You are a power system power-flow analysis assistant." in t
    assert "tool_call  load_case(case_name=\"case14\")" in t
    assert "[tool run_powerflow]   (gate: pass)" in t
    assert "plotly figure, 2 KB, omitted" in t and "xxxxxxxxxx" not in t
    assert "[verification gate]   outcome: pass_first after 1 attempt(s)" in t

    n = (run_dir / "traces" / "03_case14-plain-002-s0.narrative.txt").read_text(encoding="utf-8")
    assert "OUTCOME: ESCALATED TO A PERSON" in n
    assert "NOT EXACT (extra_step)" in n
    assert "1. LLM called load_case(case_name=\"case14\")" in n


def test_aggregate_on_empty_rows() -> None:
    agg = aggregate([])
    assert agg["n"] == 0 and agg["voltage_mae_mean"] is None
