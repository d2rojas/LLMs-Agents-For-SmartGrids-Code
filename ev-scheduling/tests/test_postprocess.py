"""postprocess lays a run set out as method folders, and gives each method its own traces.

The second half is the one that earns the test. Run ids repeat across methods
(``2018-09-17_s0_r0`` exists once per arm), so a trace lookup by file name
alone returns whichever method's file comes first. The first version did that,
and evagent's transcripts showed the no-tools system prompt and zero tool
calls. The check below is exactly the one that caught it: the system message of
every laid-out trace belongs to the method the folder is named after.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import methods
from evaluation import postprocess as pp

DAYS = ["2018-09-17", "2018-10-15", "2018-11-05"]
ARMS = ["optimum", "llm_only:structured", "evagent"]


def _system_prompt_for(arm: str) -> str:
    if arm == "evagent":
        return methods.read_text("_shared/agent_system_prompt.txt")
    return methods.read_text("_shared/llm_only_system_prompt.txt") + methods.read_text(
        "llm_only_structured/system_suffix.txt"
    )


def _make_run_set(root: Path) -> Path:
    """A small run set in the runner's own shape: rows.csv, manifest, requests, traces."""
    run_set = root / "results" / "ev_matrix_openrouter_openai_gpt-4o-mini"
    (run_set).mkdir(parents=True)
    rows = []
    with (run_set / "requests.jsonl").open("w", encoding="utf-8") as fh:
        for day in DAYS:
            rid = f"caltech-{day}-cost_question-s0"
            fh.write(json.dumps({"id": rid, "variant": "cost_question", "date": day,
                                 "text": f"Cars on {day}.\nHow much do we pay?", "day": {"sessions": []}}) + "\n")
    for arm in ARMS:
        arm_dir = {"optimum": None, "llm_only:structured": "llm_only_structured", "evagent": "evagent"}[arm]
        for day in DAYS:
            run_id = f"{day}_s0_r0"
            rid = f"caltech-{day}-cost_question-s0"
            trace_path = ""
            if arm_dir:
                sub = "agent" if arm == "evagent" else arm_dir
                tdir = run_set / "traces" / arm_dir / sub / "openrouter_openai_gpt-4o-mini"
                tdir.mkdir(parents=True, exist_ok=True)
                trace = {
                    "arm": arm, "run_id": run_id, "answer": "Answer: $1.00",
                    "messages": [{"role": "system", "content": _system_prompt_for(arm)},
                                 {"role": "user", "content": "the request"},
                                 {"role": "assistant", "content": "Answer: $1.00"}],
                    "usage": {"n_llm_calls": 1, "n_tool_calls": 1 if arm == "evagent" else 0,
                              "prompt_tokens": 10, "completion_tokens": 5, "wall_time_s": 1.0},
                    "gate": {"gate_passed": arm == "evagent", "gate_reason": "x"} if arm == "evagent" else {},
                }
                (tdir / f"{run_id}.json").write_text(json.dumps(trace), encoding="utf-8")
                # the absolute path the real runner writes, on a machine that need not be this one
                trace_path = f"/somewhere/else/results/ev_matrix_openrouter_openai_gpt-4o-mini/traces/{arm_dir}/{sub}/openrouter_openai_gpt-4o-mini/{run_id}.json"
            rows.append({
                "run_id": run_id, "arm": arm, "date": day, "site_id": "caltech", "seed": 0, "repeat": 0,
                "request_id": rid, "variant": "cost_question", "answer_kind": "cost",
                "model_resolved": "" if arm == "optimum" else "openai/gpt-4o-mini",
                "status": "ok", "error": "", "outcome": "solved" if arm == "optimum" else "wrong_unflagged",
                "outcome_reason": "x", "formulation_status": "not_checkable" if arm != "evagent" else "fail",
                "formulation_error_type": "" if arm != "evagent" else "wrong_field",
                "n_sessions_exact": "" if arm != "evagent" else 8, "n_sessions_truth": "" if arm != "evagent" else 9,
                "no_hard_violation": arm == "optimum", "max_violation_kw": 0.0, "gap_pct": 0.0, "gap_comparable": True,
                "traceability_status": "pass" if arm == "evagent" else "not_checkable", "n_numbers": 1, "n_untraceable": 0,
                "answer_status": "pass", "answer_truth": "1.00", "answer_given": "1.00",
                "cost_usd": 1.0, "cost_star_usd": 1.0, "unmet_kwh": 0.0, "peak_kw": 7.0, "pct_fully_served": 100.0,
                "gate_passed": arm == "evagent", "gate_declared_failure": False, "gate_reason": "",
                "prompt_tokens": 10, "completion_tokens": 5, "n_llm_calls": 1, "n_tool_calls": 0,
                "est_cost_usd": 0.001, "wall_s": 1.0, "trace_path": trace_path, "answer_text": "Answer: $1.00",
            })
    with (run_set / "rows.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (run_set / "run_manifest.json").write_text(json.dumps({
        "created_at": "2026-09-21T18:04:33+00:00", "site_id": "caltech", "arms": ARMS,
        "model_requested": "openrouter:openai/gpt-4o-mini", "model_resolved": "openai/gpt-4o-mini",
        "requests_digest": "sha256:abc", "seeds": [0], "repeats": 1, "synthetic": False, "data_source": "cache",
    }), encoding="utf-8")
    return run_set


@pytest.fixture
def laid_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    run_set = _make_run_set(tmp_path)
    monkeypatch.setattr(pp, "RESULTS", tmp_path / "results")
    folders = pp.postprocess(run_set, quiet=True)
    return tmp_path / "results", folders


def test_one_folder_per_arm_in_the_shared_layout(laid_out) -> None:
    results, folders = laid_out
    rel = sorted(str(f.relative_to(results)) for f in folders)
    assert rel == [
        "caltech/2026-09-21/gpt-4o-mini/evagent",
        "caltech/2026-09-21/gpt-4o-mini/llm_only_structured",
        "caltech/2026-09-21/no-llm/optimum",
    ]
    for f in folders:
        for name in ("REPORT.md", "summary.csv", "summary.json", "config.json", "requests.jsonl"):
            assert (f / name).exists(), f"{f.name} lacks {name}"


def test_every_method_gets_its_own_traces(laid_out) -> None:
    """The bug this file exists for: the system prompt in each folder is that method's."""
    results, _ = laid_out
    for folder, arm in (("gpt-4o-mini/evagent", "evagent"), ("gpt-4o-mini/llm_only_structured", "llm_only:structured")):
        traces = sorted((results / "caltech/2026-09-21" / folder / "traces").glob("*.json"))
        assert len(traces) == len(DAYS)
        for t in traces:
            payload = json.loads(t.read_text(encoding="utf-8"))
            assert payload["arm"] == arm
            assert payload["messages"][0]["content"] == _system_prompt_for(arm)


def test_requests_are_numbered_the_same_in_every_folder(laid_out) -> None:
    results, folders = laid_out
    names = {f.name: sorted(p.name for p in (f / "traces").glob("*.transcript.txt")) for f in folders}
    assert len({tuple(v) for v in names.values()}) == 1
    assert names["evagent"][0].startswith("01_")


def test_summary_counts_add_up(laid_out) -> None:
    results, folders = laid_out
    for f in folders:
        agg = json.loads((f / "summary.json").read_text(encoding="utf-8"))["aggregate"]
        assert agg["solved"] + agg["escalated"] + agg["wrong"] + agg["run_error"] == agg["n"] == len(DAYS)
        with (f / "summary.csv").open(encoding="utf-8", newline="") as fh:
            assert len(list(csv.DictReader(fh))) == len(DAYS)


def test_no_llm_rows_get_no_model_trace(laid_out) -> None:
    results, _ = laid_out
    for t in (results / "caltech/2026-09-21/no-llm/optimum/traces").glob("*.json"):
        assert "messages" not in json.loads(t.read_text(encoding="utf-8"))
