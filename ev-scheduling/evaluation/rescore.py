"""Offline re-scorer for a ``evaluation/runner.py`` run (no key, no model, no spend).

The EV counterpart of ``power-flow-agent/benchmarks/rescore.py``. A run costs
real money and its scoring definitions keep moving, so the question "what would
this run look like under the definitions we hold today" must be answerable from
the directory the run left behind. This rebuilds every scored row from the
stored requests, rows and traces, re-scores it with ``run_ev_matrix.score_row``
- the same function the run used, so the two cannot drift - and writes a full
results directory somewhere else. The source directory is never written to.

Usage (from ev-scheduling/):
    python -m evaluation.rescore results/ev_matrix_openrouter_openai_gpt-4o-mini \\
        --out-dir results/ev_matrix_openrouter_openai_gpt-4o-mini_rescored

What is rebuilt, and from what
------------------------------
* **the request**: ``requests.jsonl``, which carries the ground-truth day, the
  cap, the prices and the ground-truth answer. Nothing is regenerated from a
  seed, so a change in the request generator cannot silently rewrite the truth
  a past run was scored against. The run's ``requests_digest`` is re-derived
  and compared with the one on the rows.
* **the answer text**: the row. That is what the system actually said, and the
  answer and traceability terms are about the text.
* **the schedule**: re-derived deterministically, per arm. ``optimum`` and
  ``charge_asap`` re-run their own rule. ``llm_only`` re-parses the stored reply
  with ``methods.prompting.parse.parse_llm_schedule``. ``evagent``, ``react`` and ``plan_act`` read the parsed
  problem out of its parse trace and re-solves it with CVXPY through the agent's
  own ``_execute_solve``, with the tool arguments the model sent, so a what-if
  is replayed rather than dropped. Re-solving is deterministic; calling a model
  is not, and this module builds no client and reads no key.
* **the gate**: the row. The gate ran against the answer the model wrote and is
  not re-derivable without re-running the agent, so its verdict is carried over
  and the source is recorded. Every other term is recomputed.
* **usage, cost, wall time, model id, prompt hashes, trace paths**: the row.
  They describe the run, not the scoring.

A row whose ``status`` is not ``ok`` is carried through untouched: it was never
scored, and rescoring cannot invent a result for it.

What the output directory contains
----------------------------------
``rows.jsonl`` / ``rows.csv``, ``scoreboard.{md,csv,json}``, ``run_manifest.json``
and a copy of ``requests.jsonl``, written by the harness's own writers, so
``evaluation/report.py`` reads a rescored directory exactly as it reads a run.
The manifest gains a ``rescore`` block naming the source run, the definitions in
force, the per-row sources, and the previous scoreboard. ``rescore_rows.json``
records, per row, where its schedule came from and whether the re-solve
reproduced the cost the run reported.
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from methods.agent.parse.parse import (  # noqa: E402
    ParsedProblem,
    _parse_llm_json,
    _session_from_dict,
    parsed_problem_to_day_site_tou,
)
from evaluation.outcome import SOLVED_TERMS  # noqa: E402
from evaluation.formulation import problem_from_dict
from evaluation.requests import EVRequest, from_jsonl  # noqa: E402
from evaluation import runner as matrix  # noqa: E402

# Files a directory must have before it can be called a run.
REQUIRED_FILES: Tuple[str, ...] = ("rows.jsonl", "requests.jsonl", "run_manifest.json")

# Columns whose before-and-after values the run prints. Names as ``summarise``
# produces them.
DIFF_FIELDS: Tuple[str, ...] = (
    "formulation_exact",
    "formulation_days",
    "solved",
    "escalated",
    "wrong_unflagged",
    "traceable",
    "answer_correct",
    "feasible",
)

# A re-solve that lands this far from the cost the run reported is flagged. The
# rows store cost to six decimals and CVXPY is deterministic, so anything above
# this is a rebuild defect and not solver noise.
COST_MATCH_TOL_USD = 1e-3


class RescoreError(RuntimeError):
    """The run directory cannot be rescored, and the reason must be said."""


# --------------------------------------------------------------------------- loading


def load_run(run_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, EVRequest], Dict[str, Any]]:
    """Read a run directory's rows, requests and manifest.

    Args:
        run_dir: A directory ``run_ev_matrix`` wrote.

    Returns:
        ``(rows, requests_by_id, meta)``.

    Raises:
        RescoreError: If the directory is missing any of ``REQUIRED_FILES``, or
            holds no rows.
    """
    run_dir = Path(run_dir)
    missing = [name for name in REQUIRED_FILES if not (run_dir / name).is_file()]
    if missing:
        raise RescoreError(
            f"{run_dir} is not a run_ev_matrix results directory; missing: {', '.join(missing)}"
        )
    rows = [
        json.loads(line)
        for line in (run_dir / "rows.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise RescoreError(f"{run_dir}/rows.jsonl holds no rows")
    requests = from_jsonl(run_dir / "requests.jsonl")
    meta = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    return rows, {r.id: r for r in requests}, meta


def check_requests_digest(rows: Sequence[Dict[str, Any]], requests: Sequence[EVRequest]) -> str:
    """Re-derive the request digest and check it against the one on the rows.

    The digest is what makes "every arm saw the same inputs" checkable after the
    fact. Re-deriving it here checks something else, which matters just as much
    to a rescore: that ``requests.jsonl`` really is the list these rows were
    scored against, rather than a file that has since been regenerated.

    Args:
        rows: The stored rows.
        requests: The requests read from ``requests.jsonl``.

    Returns:
        The re-derived digest, or "" when the rows carry none to compare with.

    Raises:
        RescoreError: If the rows agree on a digest and it is not this one.
    """
    stored = {str(r.get("requests_digest") or "") for r in rows}
    stored.discard("")
    derived = matrix.requests_digest([(int(r.seed), r) for r in requests])
    if stored and derived not in stored:
        raise RescoreError(
            "requests.jsonl does not match the rows: they were scored against "
            f"{sorted(stored)} and this file digests to {derived}"
        )
    return derived


def stored_scoreboard(run_dir: Path, rows: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], str]:
    """The scoreboard the run itself printed, which is the "before" of the diff.

    Re-aggregating the stored rows with today's ``summarise`` would print the new
    definitions on both sides of the comparison and show every column as
    unchanged. The run's own ``scoreboard.json`` is the only record of what the
    numbers were, so it is preferred and the fallback says so.

    Args:
        run_dir: The directory being rescored.
        rows: The stored rows, for the fallback.

    Returns:
        ``(entries, source)`` where source is "scoreboard.json" or "re-aggregated".
    """
    path = Path(run_dir) / "scoreboard.json"
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        entries = payload.get("arms")
        if isinstance(entries, list) and entries:
            return list(entries), "scoreboard.json"
    return matrix.summarise(rows), "re-aggregated with today's summarise"


def resolve_trace(run_dir: Path, stored: Optional[str]) -> Optional[Path]:
    """The trace file for a stored path, inside the directory being rescored.

    The rows carry the absolute path the run wrote to. The copy under the
    directory being rescored is preferred, because the directory named on the
    command line is the one whose evidence is being read: a run that was copied
    elsewhere must be rescored from its own traces and not from whatever still
    sits at the original path. The stored path is the fallback, for a directory
    whose traces were never copied with it.

    Args:
        run_dir: The directory being rescored.
        stored: ``trace_path`` or ``parse_trace_path`` from the row.

    Returns:
        An existing path, or None.
    """
    if not stored:
        return None
    direct = Path(stored)
    parts = direct.parts
    if "traces" in parts:
        candidate = Path(run_dir) / Path(*parts[parts.index("traces") :])
        if candidate.is_file():
            return candidate
    return direct if direct.is_file() else None


def read_trace(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    """The JSON payload of a trace file, or None when it is absent or unreadable."""
    if path is None:
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


# --------------------------------------------------------------------------- rebuilding


def parsed_problem_from_trace(trace: Dict[str, Any]) -> Optional[ParsedProblem]:
    """The ``ParsedProblem`` the run's parse step produced, from its trace.

    Rebuilt from the raw text the model returned, through the one reader every
    method's declared problem goes through (``evaluation.formulation.problem_from_dict``),
    so the formulation term is recomputed on exactly what was extracted.

    Args:
        trace: The parse trace payload.

    Returns:
        The problem, or None when the trace carries no usable extraction.
    """
    raw = trace.get("answer") or (trace.get("trace") or {}).get("final_text") or ""
    if not str(raw).strip():
        return None
    try:
        data = _parse_llm_json(str(raw))
    except ValueError:
        return None
    return problem_from_dict(data)


def reply_from_trace(trace: Optional[Dict[str, Any]]) -> str:
    """The model's reply as the run recorded it, "" when the trace is absent."""
    if not trace:
        return ""
    return str(trace.get("answer") or (trace.get("trace") or {}).get("final_text") or "")


def tool_calls_from_trace(trace: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every tool call of an agent trace, in the order the rounds ran."""
    calls: List[Dict[str, Any]] = []
    for round_payload in ((trace or {}).get("trace") or {}).get("rounds") or []:
        for call in round_payload.get("tools") or []:
            if isinstance(call, dict):
                calls.append(call)
    return calls


def tool_outputs_from_trace(trace: Optional[Dict[str, Any]]) -> List[Any]:
    """The tool outputs of an agent trace, decoded, for traceability and the gate."""
    outputs: List[Any] = []
    for call in tool_calls_from_trace(trace):
        raw = call.get("output")
        if raw is None:
            continue
        try:
            outputs.append(json.loads(raw) if isinstance(raw, str) else raw)
        except json.JSONDecodeError:
            outputs.append(raw)
    return outputs


def _usage_from_row(row: Dict[str, Any]) -> matrix.RunUsage:
    """The run's own token accounting, carried over unchanged."""
    return matrix.RunUsage(
        prompt_tokens=int(row.get("prompt_tokens") or 0),
        completion_tokens=int(row.get("completion_tokens") or 0),
        total_tokens=int(row.get("total_tokens") or 0),
        n_llm_calls=int(row.get("n_llm_calls") or 0),
        n_tool_calls=int(row.get("n_tool_calls") or 0),
        wall_time_s=float(row.get("wall_s") or 0.0),
        n_missing_usage=int(row.get("n_missing_usage") or 0),
    )


def _gate_from_row(row: Dict[str, Any]) -> Optional[matrix.GateVerdict]:
    """The stored gate verdict, or None for an arm that has no gate."""
    passed = row.get("gate_passed")
    if passed is None:
        return None
    return matrix.GateVerdict(
        passed=bool(passed),
        declared_failure=bool(row.get("gate_declared_failure")),
        reason=str(row.get("gate_reason") or ""),
    )


def _evagent_schedule(
    request: EVRequest, parsed: ParsedProblem, tool_calls: Sequence[Dict[str, Any]]
) -> np.ndarray:
    """Re-solve the parsed problem through the agent's own solve path.

    Uses ``methods.agent.llm_agent._execute_solve`` with the arguments of the last tool
    call, so a what-if the model asked for is replayed rather than dropped. That
    function is CVXPY and nothing else: no model is called.

    Args:
        request: The request, for the ground-truth row count.
        parsed: The problem the model extracted.
        tool_calls: The agent trace's tool calls, in order.

    Returns:
        The schedule, with its rows aligned to the ground-truth day.

    Raises:
        RescoreError: If the re-solve does not return a schedule.
    """
    from methods.agent.llm_agent import _execute_solve

    day, site, tou = parsed_problem_to_day_site_tou(parsed)
    arguments: Dict[str, Any] = {}
    for call in tool_calls:
        if call.get("name") == "solve_ev_schedule" and isinstance(call.get("arguments"), dict):
            arguments = dict(call["arguments"])
    solve_result, _tool_result, _day, _site = _execute_solve(day, site, tou, arguments)
    if not solve_result.success:
        raise RescoreError(f"the re-solve returned {solve_result.message!r}")
    return matrix._align_rows(
        np.asarray(solve_result.schedule, dtype=float), len(request.day.sessions)
    )


def rebuild_output(
    row: Dict[str, Any], request: EVRequest, run_dir: Path
) -> Tuple[matrix.ArmOutput, Dict[str, Any]]:
    """Rebuild one row's ``ArmOutput`` from the stored artefacts.

    Args:
        row: The stored row.
        request: The request it was scored against.
        run_dir: The directory being rescored, for resolving trace paths.

    Returns:
        ``(output, sources)``. ``sources`` names where the schedule, the answer
        text, the tool outputs and the gate came from, for ``rescore_rows.json``.

    Raises:
        RescoreError: If the arm is unknown, or its schedule cannot be rebuilt.
    """
    arm_name = str(row.get("arm"))
    arm = matrix.ARMS.get(arm_name)
    if arm is None:
        raise RescoreError(f"unknown arm {arm_name!r}; it is not in the registry")
    answer_text = str(row.get("answer_text") or "")
    sources: Dict[str, Any] = {
        "arm": arm_name,
        "answer_text": "row",
        "gate": "row" if row.get("gate_passed") is not None else "none",
        "usage": "row",
    }
    ctx = matrix.RunContext(
        arm=arm,
        request=request,
        seed=int(row.get("seed") or 0),
        repeat=int(row.get("repeat") or 0),
        spec=matrix.parse_model_spec(str(row.get("model_spec") or matrix.DEFAULT_MODEL)),
        model_requested=str(row.get("model_requested") or ""),
        trace_dir=Path(run_dir) / "traces",
        run_id=str(row.get("run_id") or ""),
        client=None,          # no client is ever built here
        write_trace=False,    # the run's traces are the evidence and stay as they are
    )

    tool_outputs: List[Any] = []
    prior_tool_outputs: List[Any] = []
    parsed_problem: Any = None
    repairs: Optional[Dict[str, Any]] = None
    parse_success: Optional[bool] = None

    if arm_name in ("optimum", "charge_asap", "rule_based"):
        produced = matrix.RUNNERS[arm_name](ctx)
        schedule = produced.schedule
        tool_outputs = list(produced.tool_outputs)
        parsed_problem = produced.parsed_problem
        if arm_name == "rule_based":
            # the rule reads the same text again; its refusal, if any, is the same refusal
            answer_text = produced.answer_text
        sources["schedule"] = "rule_rerun"
        sources["tool_outputs"] = "rule_rerun"
    elif arm_name.startswith("llm_only"):
        # The reply is in the trace; the row's answer_text is the whole reply
        # only for runs before 2026-09-28, and is the fallback for a run whose
        # trace was not copied with it.
        reply = reply_from_trace(read_trace(resolve_trace(run_dir, row.get("trace_path")))) or answer_text
        read = matrix.read_reply(reply, request.day)
        schedule = np.asarray(read.schedule.schedule, dtype=float)
        repairs = read.schedule.repairs.to_dict()
        parse_success = bool(read.schedule.success)
        parsed_problem = problem_from_dict(read.formulation, n_steps=request.day.n_steps, dt_hours=request.day.dt_hours)
        answer_text = matrix.llm_only_answer_text(read, reply)
        sources["schedule"] = f"reply_reparsed_as_{read.format}"
        sources["tool_outputs"] = "none"
        sources["parsed_problem"] = "reply" if parsed_problem is not None else "none"
    elif arm_name in ("evagent", "react", "plan_act"):
        # The two agent rows leave the same artefacts: a parse trace and an
        # agent trace with the tool calls. Only the gate differs, and the gate
        # is read from the row, where a react row carries none.
        parse_trace = read_trace(resolve_trace(run_dir, row.get("parse_trace_path")))
        if parse_trace is None:
            raise RescoreError("the parse trace is missing, so the parsed problem is not rebuildable")
        parsed_problem = parsed_problem_from_trace(parse_trace)
        if parsed_problem is None:
            raise RescoreError("the parse trace carries no usable extraction")
        agent_trace = read_trace(resolve_trace(run_dir, row.get("trace_path")))
        calls = tool_calls_from_trace(agent_trace)
        all_outputs = tool_outputs_from_trace(agent_trace)
        tool_outputs = all_outputs[-1:] if all_outputs else []
        prior_tool_outputs = all_outputs[:-1] if len(all_outputs) > 1 else []
        if row.get("gate_declared_failure"):
            # The gate declared a failure, so the run surfaced no schedule and no
            # numbers. Re-solving the parse would rebuild a schedule the system
            # deliberately did not stand behind, and score the day on it. What
            # was surfaced is what is rescored.
            schedule = np.zeros((len(request.day.sessions), request.day.n_steps), dtype=float)
            sources["schedule"] = "declared_failure_no_schedule"
        else:
            schedule = _evagent_schedule(request, parsed_problem, calls)
            sources["schedule"] = "resolved_from_parse_trace"
        sources["tool_outputs"] = "agent_trace" if all_outputs else "missing"
        sources["parsed_problem"] = "parse_trace"
    else:
        raise RescoreError(f"arm {arm_name!r} has no offline rebuild path")

    gate_row = {name: row.get(name) for name in matrix.GATE_ROW_FIELDS if row.get(name) is not None}
    output = matrix.ArmOutput(
        schedule=np.asarray(schedule, dtype=float),
        answer_text=answer_text,
        tool_outputs=tool_outputs,
        prior_tool_outputs=prior_tool_outputs,
        parsed_problem=parsed_problem,
        gate=_gate_from_row(row),
        gate_row=gate_row,
        usage=_usage_from_row(row),
        model_resolved=str(row.get("model_resolved") or ""),
        prompt_hash=str(row.get("prompt_hash") or ""),
        system_prompt_hash=str(row.get("system_prompt_hash") or ""),
        trace_path=Path(row["trace_path"]) if row.get("trace_path") else None,
        parse_trace_path=Path(row["parse_trace_path"]) if row.get("parse_trace_path") else None,
        repairs=repairs,
        parse_success=parse_success,
    )
    return output, sources


# --------------------------------------------------------------------------- rows


def rescore_row(
    row: Dict[str, Any],
    requests: Dict[str, EVRequest],
    run_dir: Path,
    *,
    traceability_policy: str,
    gap_tol_pct: float,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Re-score one stored row, or carry it through when it was never scored.

    Args:
        row: The stored row.
        requests: Requests by id, from ``requests.jsonl``.
        run_dir: The directory being rescored.
        traceability_policy: One of ``matrix.TRACEABILITY_POLICIES``.
        gap_tol_pct: Two-sided cost-gap tolerance, per cent.

    Returns:
        ``(new_row, sources)``. ``sources`` carries the rebuild provenance plus
        ``cost_usd_matches``, which says whether the re-derived schedule cost
        the same as the run reported. A row that could not be rebuilt comes back
        as a ``status="rescore_failed"`` row with the reason, never dropped.
    """
    normalised = {name: row.get(name) for name in matrix.ROW_FIELDS}
    identity = {
        "run_id": row.get("run_id"),
        "arm": row.get("arm"),
        "date": row.get("date"),
        "request_id": row.get("request_id"),
    }
    if row.get("status") != "ok":
        return normalised, {**identity, "rescored": False, "reason": "the row was never scored"}

    request = requests.get(str(row.get("request_id")))
    if request is None:
        normalised["status"] = "rescore_failed"
        normalised["error"] = f"no request {row.get('request_id')!r} in requests.jsonl"
        return normalised, {**identity, "rescored": False, "reason": normalised["error"]}

    try:
        output, sources = rebuild_output(row, request, run_dir)
        ctx = matrix.RunContext(
            arm=matrix.ARMS[str(row["arm"])],
            request=request,
            seed=int(row.get("seed") or 0),
            repeat=int(row.get("repeat") or 0),
            spec=matrix.parse_model_spec(str(row.get("model_spec") or matrix.DEFAULT_MODEL)),
            model_requested=str(row.get("model_requested") or ""),
            trace_dir=Path(run_dir) / "traces",
            run_id=str(row.get("run_id") or ""),
            client=None,
            write_trace=False,
        )
        scored = matrix.score_row(
            ctx, output, traceability_policy=traceability_policy, gap_tol_pct=gap_tol_pct
        )
    except Exception as exc:  # noqa: BLE001 - a failed rebuild is a row, not a crash
        normalised["status"] = "rescore_failed"
        normalised["error"] = f"{type(exc).__name__}: {exc}"
        return normalised, {**identity, "rescored": False, "reason": normalised["error"]}

    new_row = matrix.build_row(
        ctx,
        output,
        scored,
        status="ok",
        error="",
        requests_digest=str(row.get("requests_digest") or ""),
        synthetic=bool(row.get("synthetic")),
        data_source=str(row.get("data_source") or ""),
        est_cost_usd=float(row.get("est_cost_usd") or 0.0),
        traceability_policy=traceability_policy,
    )
    old_cost = row.get("cost_usd")
    new_cost = new_row.get("cost_usd")
    matches = (
        None
        if old_cost is None or new_cost is None
        else abs(float(new_cost) - float(old_cost)) <= COST_MATCH_TOL_USD
    )
    sources.update(
        {
            **identity,
            "rescored": True,
            "cost_usd_run": old_cost,
            "cost_usd_rescored": new_cost,
            "cost_usd_matches": matches,
            "outcome_run": row.get("outcome"),
            "outcome_rescored": new_row.get("outcome"),
        }
    )
    return new_row, sources


# --------------------------------------------------------------------------- reporting


def diff_lines(
    old: Sequence[Dict[str, Any]], new: Sequence[Dict[str, Any]]
) -> List[str]:
    """One block per arm: the columns that moved, then the ones that did not.

    Args:
        old: The run's scoreboard entries, as ``summarise`` produced them.
        new: The rescored entries.

    Returns:
        Lines ready to print. A column absent from the old scoreboard is shown
        as ``n/a -> ...``, which is what a newly added column looks like.
    """
    by_arm = {str(e.get("arm")): e for e in old}
    lines: List[str] = []
    for entry in new:
        arm = str(entry.get("arm"))
        before = by_arm.get(arm, {})
        changed, same = [], []
        for field in DIFF_FIELDS:
            a, b = before.get(field), entry.get(field)
            if matrix._fmt_rate(a) == matrix._fmt_rate(b):
                same.append(f"{field}={matrix._fmt_rate(b)}")
            else:
                changed.append(f"{field}: {matrix._fmt_rate(a)} -> {matrix._fmt_rate(b)}")
        lines.append(f"[{arm}]")
        lines.extend(f"    {line}" for line in changed)
        if same:
            lines.append("    unchanged: " + ", ".join(same))
    return lines


# --------------------------------------------------------------------------- run level


def rescore_run(
    run_dir: Path,
    out_dir: Path,
    *,
    traceability_policy: Optional[str] = None,
    gap_tol_pct: Optional[float] = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Rescore a whole run directory into a new one.

    Args:
        run_dir: The completed run.
        out_dir: Where to write. Must not be the run directory or inside it: a
            rescore that overwrote the evidence would be the one mistake this
            module must never make.
        traceability_policy: Override the run's policy. Defaults to the run's.
        gap_tol_pct: Override the run's gap tolerance. Defaults to the run's.
        verbose: Print the before-and-after block.

    Returns:
        ``{"rows", "summary", "sources", "out_dir", "lines"}``.

    Raises:
        RescoreError: If the source is not a run, or the output would land on it.
    """
    started = time.time()
    run_dir = Path(run_dir).resolve()
    out_dir = Path(out_dir).resolve()
    if out_dir == run_dir or run_dir in out_dir.parents:
        raise RescoreError(
            f"refusing to write into {run_dir}: a rescore writes a new directory and never "
            "touches the run it reads"
        )

    rows, requests, meta = load_run(run_dir)
    if meta.get("synthetic") and matrix._is_inside(out_dir, matrix.REPO_ROOT):
        raise RescoreError(
            "refusing to write the rescore of a synthetic smoke test inside the repository.\n"
            f"  requested: {out_dir}\n"
            f"  repository: {matrix.REPO_ROOT}\n"
            "A rescore of fixture days is no more citable than the run it reads. Pass --out-dir "
            "pointing outside the repository."
        )
    digest = check_requests_digest(rows, list(requests.values()))
    policy = str(traceability_policy or meta.get("traceability_policy") or "grounded_only")
    if policy not in matrix.TRACEABILITY_POLICIES:
        raise RescoreError(f"unknown traceability policy {policy!r}")
    tolerance = float(gap_tol_pct if gap_tol_pct is not None else meta.get("gap_tol_pct") or matrix.GAP_TOL_PCT)

    new_rows: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    for row in rows:
        new_row, source = rescore_row(
            row, requests, run_dir, traceability_policy=policy, gap_tol_pct=tolerance
        )
        new_rows.append(new_row)
        sources.append(source)

    old_summary, old_source = stored_scoreboard(run_dir, rows)
    summary = matrix.summarise(new_rows)
    n_failed = sum(1 for r in new_rows if r.get("status") != "ok")
    mismatched = [s for s in sources if s.get("cost_usd_matches") is False]

    new_meta = {
        **meta,
        "n_failed": n_failed,
        "traceability_policy": policy,
        "gap_tol_pct": tolerance,
        "solved_terms": list(SOLVED_TERMS),
        "formulation_aggregation": matrix.FORMULATION_AGGREGATION,
        "out_dir": str(out_dir),
        "rescore": {
            "source_run": str(run_dir),
            "rescored_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tool": "evaluation/rescore.py",
            "requests_digest": digest,
            "n_rows": len(new_rows),
            "n_rescored": sum(1 for s in sources if s.get("rescored")),
            "n_rescore_failed": sum(1 for r in new_rows if r.get("status") == "rescore_failed"),
            "n_cost_mismatch": len(mismatched),
            "model_calls": 0,
            "usd_spent": 0.0,
            "solved_terms": list(SOLVED_TERMS),
            "formulation_aggregation": matrix.FORMULATION_AGGREGATION,
            "previous_scoreboard": old_summary,
            "previous_scoreboard_source": old_source,
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    matrix.write_rows(out_dir, new_rows)
    matrix.write_scoreboard(out_dir, summary, new_meta)
    matrix.write_manifest(out_dir, new_meta)
    if new_meta.get("synthetic"):
        matrix.write_smoke_sentinel(out_dir, new_meta)
    shutil.copyfile(run_dir / "requests.jsonl", out_dir / "requests.jsonl")
    (out_dir / "rescore_rows.json").write_text(
        json.dumps(matrix._jsonable(sources), indent=2), encoding="utf-8"
    )

    lines = [
        f"== {run_dir}  ({len(new_rows)} rows, {time.time() - started:.1f}s, no model call, $0.00)",
        f"   solved = {' AND '.join(SOLVED_TERMS)} AND gate; "
        f"formulation aggregated {matrix.FORMULATION_AGGREGATION}",
        f"   rescored={new_meta['rescore']['n_rescored']} "
        f"failed={new_meta['rescore']['n_rescore_failed']} "
        f"cost_mismatch={len(mismatched)}",
        f"   before = {old_source}, after = this rescore",
    ]
    lines.extend(diff_lines(old_summary, summary))
    lines.append(f"   written: {out_dir}/rows.jsonl (+ scoreboard.*, run_manifest.json)")
    if verbose:
        print("\n".join(lines))
    return {
        "rows": new_rows,
        "summary": summary,
        "previous_summary": old_summary,
        "sources": sources,
        "out_dir": out_dir,
        "lines": lines,
    }


# --------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    """The command line: one run in, one new directory out."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("run_dir", help="a directory evaluation/runner.py wrote")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="where to write; defaults to <run_dir>_rescored next to the run",
    )
    parser.add_argument(
        "--traceability-policy",
        choices=list(matrix.TRACEABILITY_POLICIES),
        default=None,
        help="override the run's policy; defaults to the one the run used",
    )
    parser.add_argument(
        "--gap-tol-pct",
        type=float,
        default=None,
        help="override the cost-gap tolerance, per cent; defaults to the run's",
    )
    parser.add_argument("--quiet", action="store_true", help="write the artefacts, print nothing")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Rescore one run. Returns non-zero when a row could not be rebuilt."""
    args = build_parser().parse_args(argv)
    run_dir = Path(args.run_dir).resolve()
    out_dir = Path(args.out_dir) if args.out_dir else run_dir.parent / f"{run_dir.name}_rescored"
    try:
        result = rescore_run(
            run_dir,
            out_dir,
            traceability_policy=args.traceability_policy,
            gap_tol_pct=args.gap_tol_pct,
            verbose=not args.quiet,
        )
    except RescoreError as exc:
        print(f"ev_rescore: {exc}", file=sys.stderr)
        return 2
    failed = sum(1 for r in result["rows"] if r.get("status") == "rescore_failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
