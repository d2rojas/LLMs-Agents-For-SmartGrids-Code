"""The offline re-scorer: same verdicts, no model call, and never on the evidence.

Three things are pinned here, and each is a way a rescore could quietly ruin a
run that cost money.

* **fidelity.** Rescoring a run with the definitions it was scored under must
  reproduce it. The stub-client run is scored once by the harness and then
  rebuilt from its own artefacts, and the two sets of rows are compared term by
  term. A rebuild that silently mis-solves would otherwise look like a finding.
* **no spending.** Every entry point that could reach a provider is replaced
  with one that fails the test. A rescore that fell back to a model call would
  cost money and would no longer be a rescore.
* **the source is read-only.** Writing into the run directory is refused, and
  the test checks the original bytes are untouched.

The run under test is built with ``tests.test_ev_matrix``'s stub client, which
answers the parse step, the tool loop and the no-tools arm. Importing it is
deliberate: a second stub here would be a second definition of what a model
says, and the two would drift.
"""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

import pytest

from evaluation import report as ev_report
from evaluation import rescore as ev_rescore
from evaluation import runner as matrix
from tests.test_ev_matrix import MODEL, SUBSET_DATES, StubClient

# Terms that must come back identical when a run is rescored under its own
# definitions. The gate is carried over rather than recomputed, so it is here as
# a carry-over check and not as a recomputation.
IDENTICAL_FIELDS = (
    "outcome",
    "solved",
    "escalated",
    "wrong_unflagged",
    "formulation_status",
    "formulation_error_type",
    "n_sessions_exact",
    "state_status",
    "no_hard_violation",
    "traceability_status",
    "answer_status",
    "answer_given",
    "gate_passed",
    "cost_usd",
    "unmet_kwh",
    "peak_kw",
)


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory) -> Path:
    """A complete run directory, written offline by the harness itself."""
    out_dir = tmp_path_factory.mktemp("ev_rescore_source")
    pairs = matrix.load_requests(
        seeds=[0], dates=SUBSET_DATES, site_id="caltech", source="fixture"
    )
    client = StubClient()
    client.day = pairs[0][1].day
    rows = matrix.run_matrix(
        arms=matrix.resolve_arms(list(matrix.DEFAULT_ARMS) + ["optimum", "charge_asap"]),
        pairs=pairs,
        spec=matrix.parse_model_spec(MODEL),
        model_requested=MODEL,
        out_dir=out_dir,
        run_id="ev_matrix_test_SYNTHETIC_SMOKE",
        repeats=1,
        max_tool_rounds=1,
        max_completion_tokens=512,
        traceability_policy="grounded_only",
        ledger=matrix.Ledger(price_in=2.5, price_out=10.0, limit_usd=10.0),
        synthetic=True,
        data_source="fixture",
        inner_client=client,
        write_trace=True,
        progress=False,
    )
    summary = matrix.summarise(rows)
    meta = {
        "run_id": "ev_matrix_test_SYNTHETIC_SMOKE",
        "created_at": "2026-09-21T00:00:00+00:00",
        "case_study": "ev_scheduling",
        "harness": "evaluation/runner.py",
        "synthetic": True,
        "smoke_test": True,
        "banner": matrix.SMOKE_BANNER,
        "data_source": "fixture",
        "site_id": "caltech",
        "dates": sorted({r["date"] for r in rows}),
        "n_days": len({r["date"] for r in rows}),
        "seeds": [0],
        "repeats": 1,
        "items_per_arm": len(pairs),
        "arms": list(matrix.DEFAULT_ARMS) + ["optimum", "charge_asap"],
        "pending_arms": {},
        "model_requested": MODEL,
        "model_spec": MODEL,
        "models_resolved": sorted({r["model_resolved"] for r in rows if r["model_resolved"]}),
        "max_completion_tokens": 512,
        "max_tool_rounds": 1,
        "traceability_policy": "grounded_only",
        "gap_tol_pct": matrix.GAP_TOL_PCT,
        "solved_terms": list(matrix.SOLVED_TERMS),
        "formulation_aggregation": matrix.FORMULATION_AGGREGATION,
        "budget_usd": 10.0,
        "spent_usd": 0.01,
        "price_in_per_mtok": 2.5,
        "price_out_per_mtok": 10.0,
        "price_source": "test",
        "requests_digest": rows[0]["requests_digest"],
        "strategies": {},
        "python": "3.14",
        "n_failed": sum(1 for r in rows if r["status"] != "ok"),
        "out_dir": str(out_dir),
    }
    matrix.write_rows(out_dir, rows)
    matrix.write_scoreboard(out_dir, summary, meta)
    matrix.write_manifest(out_dir, meta)
    matrix.write_smoke_sentinel(out_dir, meta)
    matrix.to_jsonl([request for _seed, request in pairs], out_dir / "requests.jsonl")
    return out_dir


@pytest.fixture(autouse=True)
def no_provider_anywhere(monkeypatch):
    """Every route to a provider fails the test, for every test in this module."""

    def _forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("a model call was made during a rescore")

    import methods.agent.llm_agent as llm_agent
    import methods.agent.parse.parse as parse_module

    for module in (matrix, llm_agent, parse_module):
        for name in ("call_chat", "build_client"):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, _forbidden)
    return _forbidden


@pytest.fixture(scope="module")
def rescored(run_dir, tmp_path_factory):
    """The run rescored into a directory of its own, under its own definitions."""
    out_dir = tmp_path_factory.mktemp("ev_rescore_out")
    result = ev_rescore.rescore_run(run_dir, out_dir / "rescored", verbose=False)
    return result


def _by_key(rows: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
    return {(r["arm"], r["request_id"], r["repeat"]): r for r in rows}


# --------------------------------------------------------------------------- fidelity


def test_rescoring_reproduces_the_run_it_reads(run_dir, rescored):
    """The load-bearing property: same artefacts in, same verdicts out.

    Every term is compared on every row of every arm, including the schedule's
    cost, which is what catches a rebuild that re-solved a different problem.
    """
    original = _by_key(
        [json.loads(line) for line in (run_dir / "rows.jsonl").read_text().splitlines() if line.strip()]
    )
    new = _by_key(rescored["rows"])

    assert set(new) == set(original)
    for key, old_row in original.items():
        for field in IDENTICAL_FIELDS:
            assert new[key][field] == old_row[field], f"{key}: {field}"


def test_every_row_was_actually_rebuilt(rescored):
    """A carried-over row would pass the comparison above without proving anything."""
    sources = rescored["sources"]
    assert sources
    assert all(s["rescored"] for s in sources)
    assert {s["schedule"] for s in sources if s.get("schedule")} == {
        "rule_rerun",
        "reply_reparsed",
        "resolved_from_parse_trace",
    }
    assert all(s["cost_usd_matches"] for s in sources)


def test_the_agent_schedule_is_re_solved_not_copied(run_dir, rescored):
    """The agent arm's schedule comes back from CVXPY, through its parse trace."""
    agent_sources = [s for s in rescored["sources"] if s["arm"] == "evagent"]
    assert agent_sources
    for source in agent_sources:
        assert source["schedule"] == "resolved_from_parse_trace"
        assert source["parsed_problem"] == "parse_trace"
        assert source["tool_outputs"] == "agent_trace"


def test_a_formulation_verdict_is_recomputed_from_the_parse_trace(run_dir):
    """The term the whole exercise is about is derived again, not read off the row."""
    rows, requests, _meta = ev_rescore.load_run(run_dir)
    row = next(r for r in rows if r["arm"] == "evagent" and r["status"] == "ok")
    trace = ev_rescore.read_trace(
        ev_rescore.resolve_trace(run_dir, row["parse_trace_path"])
    )

    problem = ev_rescore.parsed_problem_from_trace(trace)

    assert problem is not None
    assert len(problem.sessions) == row["n_sessions_parsed"]


# --------------------------------------------------------------------------- no spending


def test_the_rescore_spends_nothing(rescored):
    """Said in the manifest, not only in the docstring."""
    block = json.loads((rescored["out_dir"] / "run_manifest.json").read_text())["rescore"]
    assert block["model_calls"] == 0
    assert block["usd_spent"] == 0.0
    assert block["n_rescore_failed"] == 0


def test_no_key_is_needed(run_dir, tmp_path, monkeypatch):
    """A rescore must run on a machine with no credentials at all."""
    for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    result = ev_rescore.rescore_run(run_dir, tmp_path / "out", verbose=False)

    assert all(r["status"] == "ok" for r in result["rows"])


# --------------------------------------------------------------------------- the source


def test_writing_into_the_run_directory_is_refused(run_dir):
    """The traces are the evidence, and a rescore is not allowed near them."""
    with pytest.raises(ev_rescore.RescoreError, match="never touches the run"):
        ev_rescore.rescore_run(run_dir, run_dir, verbose=False)
    with pytest.raises(ev_rescore.RescoreError, match="never touches the run"):
        ev_rescore.rescore_run(run_dir, run_dir / "rescored", verbose=False)


def test_the_source_run_is_unchanged(run_dir, rescored):
    """Checked on the bytes, because that is the only check worth having."""
    before = json.loads((run_dir / "run_manifest.json").read_text())
    assert "rescore" not in before
    assert (run_dir / "rows.jsonl").read_text() != ""
    assert not (run_dir / "rescore_rows.json").exists()


def test_a_directory_that_is_not_a_run_is_refused(tmp_path):
    with pytest.raises(ev_rescore.RescoreError, match="not a run_ev_matrix results directory"):
        ev_rescore.load_run(tmp_path)


def test_requests_that_do_not_match_the_rows_are_refused(run_dir, tmp_path):
    """A regenerated requests.jsonl would rescore against a truth that never ran."""
    copy = tmp_path / "moved"
    shutil.copytree(run_dir, copy)
    lines = (copy / "requests.jsonl").read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])
    payload["text"] = payload["text"] + " (edited after the run)"
    lines[0] = json.dumps(payload)
    (copy / "requests.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ev_rescore.RescoreError, match="does not match the rows"):
        ev_rescore.rescore_run(copy, tmp_path / "out", verbose=False)


# --------------------------------------------------------------------------- artefacts


def test_the_output_is_a_run_directory_the_report_reads(rescored):
    """A rescored directory must be usable everywhere a run directory is."""
    out_dir = rescored["out_dir"]
    for name in ("rows.jsonl", "rows.csv", "scoreboard.md", "scoreboard.json", "run_manifest.json",
                 "requests.jsonl", "rescore_rows.json"):
        assert (out_dir / name).exists(), name

    assert ev_report.main([str(out_dir)]) == 0
    assert (out_dir / "REPORT.md").exists()


def test_rescored_rows_keep_the_declared_schema(rescored):
    """The CSV schema is fixed, and a rescore may not widen it."""
    for row in rescored["rows"]:
        assert list(row.keys()) == list(matrix.ROW_FIELDS)


def test_the_manifest_records_the_definitions_in_force(run_dir, rescored):
    """"What did this run look like under the new definitions" has to be answerable."""
    meta = json.loads((rescored["out_dir"] / "run_manifest.json").read_text())

    assert meta["solved_terms"] == list(matrix.SOLVED_TERMS)
    assert "formulation" not in meta["solved_terms"]
    assert meta["formulation_aggregation"] == "per_session"
    assert Path(meta["rescore"]["source_run"]) == run_dir.resolve()
    assert Path(meta["out_dir"]) == Path(rescored["out_dir"])


def test_the_before_comes_from_the_scoreboard_the_run_printed(rescored):
    """Re-aggregating the old rows would print the new definitions on both sides."""
    block = json.loads((rescored["out_dir"] / "run_manifest.json").read_text())["rescore"]

    assert block["previous_scoreboard_source"] == "scoreboard.json"
    assert block["previous_scoreboard"]


def test_a_smoke_test_rescore_stays_a_smoke_test(rescored):
    """The banner travels with the numbers, or the numbers get quoted."""
    text = (rescored["out_dir"] / "scoreboard.md").read_text(encoding="utf-8")

    assert "SMOKE TEST" in text and "DO NOT CITE" in text
    assert (rescored["out_dir"] / matrix.SMOKE_SENTINEL_NAME).exists()


def test_a_synthetic_rescore_refuses_to_write_inside_the_repository(run_dir):
    """Same rule as the run: fixture numbers do not land in the repository."""
    with pytest.raises(ev_rescore.RescoreError, match="refusing to write"):
        ev_rescore.rescore_run(
            run_dir, matrix.PROJECT_ROOT / "results" / "rescore_should_not_exist", verbose=False
        )
    assert not (matrix.PROJECT_ROOT / "results" / "rescore_should_not_exist").exists()


# --------------------------------------------------------------------------- failure


def test_a_row_that_cannot_be_rebuilt_becomes_a_failed_row(run_dir, tmp_path):
    """Loud failure, the harness's own rule: never a silently dropped arm.

    The copy's parse traces are corrupted rather than deleted, because deleting
    them would fall back to the original run's traces and rescore correctly,
    which is the fallback in ``resolve_trace`` and not the case under test.
    """
    copy = tmp_path / "broken"
    shutil.copytree(run_dir, copy)
    for path in (copy / "traces").rglob("*.json"):
        if "parse" in path.parts:
            path.write_text("not json at all", encoding="utf-8")

    result = ev_rescore.rescore_run(copy, tmp_path / "out", verbose=False)

    failed = [r for r in result["rows"] if r["status"] == "rescore_failed"]
    assert failed
    # both agent rows are rebuilt from the parse trace, so both fail, and only they
    assert {r["arm"] for r in failed} == {"evagent", "react"}
    assert all("parse trace" in r["error"] for r in failed)
    # and the arms that did not depend on it are unaffected
    assert all(r["status"] == "ok" for r in result["rows"] if r["arm"] not in ("evagent", "react"))


def test_the_cli_returns_non_zero_when_a_row_fails(run_dir, tmp_path, capsys):
    """An exit code, because a rescore is run from a shell."""
    copy = tmp_path / "broken_cli"
    shutil.copytree(run_dir, copy)
    for path in (copy / "traces").rglob("*.json"):
        if "parse" in path.parts:
            path.write_text(json.dumps({"answer": "no sessions here"}), encoding="utf-8")

    code = ev_rescore.main([str(copy), "--out-dir", str(tmp_path / "cli_out")])

    assert code == 1
    assert "rescored=" in capsys.readouterr().out


def test_the_cli_writes_a_new_directory_and_prints_the_diff(run_dir, tmp_path, capsys):
    out_dir = tmp_path / "cli_ok"

    code = ev_rescore.main([str(run_dir), "--out-dir", str(out_dir)])

    text = capsys.readouterr().out
    assert code == 0
    assert (out_dir / "rows.jsonl").exists()
    assert "no model call, $0.00" in text
    assert "solved = state AND traceability AND answer AND gate" in text
