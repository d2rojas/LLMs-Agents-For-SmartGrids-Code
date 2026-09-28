"""LLM-driven agent: natural-language problem + tool access to the CVXPY solver.

The agent receives:
  1. A natural-language description of the EV charging problem (sessions,
     site cap, TOU rates, time horizon) and what it is asked to do.
  2. Access to a single tool, solve_ev_schedule, that runs the CVXPY
     optimizer on the problem described in the prompt.

The LLM decides whether to call the tool:
  - Scheduling / optimization requests → tool is called.
  - What-if / constraint-change requests → tool is called with modified params.
  - Qualitative, explanatory, or conceptual questions → answered directly.

If the LLM does not call the tool the solver is NOT run; the caller receives
a zero schedule with feasible=False and the LLM's direct text answer.

Verification gate
-----------------
An answer that quotes solver numbers is not surfaced until ``methods/agent/validate/gate.py``
accepts it. This module owns the loop, the gate owns the decision and the words:
verify the answer, on "retry" hand the gate's message back to the model as a user
turn and let it answer once more, and on a second failure return the gate's
declared-failure text with no schedule and no numbers. During the retry a solver
call that would change the problem (a charger disabled, a different cap, an added
session) is blocked by ``retry_changes_problem``, so the second attempt cannot
pass verification by answering an easier question.

The gate judges the problem that was actually posed. A what-if call solves a
modified day and site, and ``_execute_solve`` returns both so the constraint
check and the gate read the same problem the solver read.
"""

import copy
import json
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import numpy as np

import methods

from methods.agent.explain.explain import extract_facts, generate_explanation
from methods.agent.optimize.call_solver import optimize
from methods.agent.validate.gate import (
    DECLARE_FAILURE,
    MAX_VERIFICATION_ATTEMPTS,
    RETRY,
    GateResult,
    decide,
    retry_changes_problem,
    split_tool_outputs,
    verify_answer,
)
from methods.agent.validate.validate import validate
from methods.prompting.prompt import build_prompt_for_agent
from config.llm import (
    ModelSpec,
    RunRecorder,
    RunUsage,
    build_client,
    call_chat,
    parse_model_spec,
)
from config.site import SiteConfig, TOUConfig
from solver.checker import CheckResult
from data.format.schema import DaySessions, Session
from evaluation.metrics import pct_fully_served
from evaluation.outcome import GateVerdict
from solver.solver import SolveResult

# Tool calls the model may make while answering the gate's retry message. One is
# enough to re-solve the problem as posed; more would be a new exploration.
RETRY_TOOL_BUDGET = 1

# Returned to the model instead of a solve when the retry would change the
# problem. It is recorded as a tool output, so a blocked retry is visible in the
# trace rather than looking like a call that never happened.
BLOCKED_RETRY_ERROR = (
    "Blocked: this call changes the problem (site cap, disabled chargers, or extra "
    "sessions) instead of re-solving the one posed. Answer for the problem as posed."
)


# ---------------------------------------------------------------------------
# Tool definition (OpenAI function schema)
# ---------------------------------------------------------------------------

_SOLVE_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "solve_ev_schedule",
        "description": (
            "Run the CVXPY convex optimizer on the EV charging problem described in the conversation. "
            "Call this tool ONLY when the user's request requires computing or optimizing a charging "
            "schedule — for example: minimizing cost, reducing peak load, or exploring a what-if "
            "scenario (e.g. a charger offline, a lower site cap, or an extra session). "
            "Do NOT call this tool for general questions, definitions, or conceptual explanations; "
            "answer those directly. "
            "Returns a metrics summary: success, total_cost_usd, peak_load_kw, total_unmet_kwh, "
            "pct_fully_served. The schedule is stored internally."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "penalty_unmet": {
                    "type": "number",
                    "description": (
                        "Penalty ($/kWh) applied to unmet energy in the objective. "
                        "Default 1000000 strongly prioritises full energy delivery."
                    ),
                },
                "disabled_chargers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "What-if: list of charger IDs to disable (set max power to 0). "
                        "Use when the user asks 'what if charger X is offline?' or similar. "
                        "Example: [\"CA-322\", \"CA-489\"]"
                    ),
                },
                "site_cap_kw": {
                    "type": "number",
                    "description": (
                        "What-if: override the site power cap (kW) for this solve. "
                        "Use when the user asks 'what if the site cap is reduced to X kW?' "
                        "or 'what happens if we lower the cap?'. Must be positive."
                    ),
                },
                "extra_sessions": {
                    "type": "array",
                    "description": (
                        "What-if: additional charging sessions to inject into the problem. "
                        "Use when the user asks 'what if we add another EV?' or similar. "
                        "Each element must have: arrival_idx (int), departure_idx (int), "
                        "energy_kwh (float), max_power_kw (float). "
                        "charger_id and session_id default to 'extra-0', 'extra-1', etc."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "arrival_idx": {"type": "integer"},
                            "departure_idx": {"type": "integer"},
                            "energy_kwh": {"type": "number"},
                            "max_power_kw": {"type": "number"},
                        },
                        "required": ["arrival_idx", "departure_idx", "energy_kwh", "max_power_kw"],
                    },
                },
            },
            "required": [],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

def _apply_what_if(
    day: DaySessions,
    site: SiteConfig,
    tool_arguments: Dict[str, Any],
) -> tuple[DaySessions, SiteConfig]:
    """Apply what-if overrides from tool arguments and return modified copies.

    Handles three optional what-if parameters:
      - disabled_chargers: zero out max_power_kw for sessions on those chargers.
      - site_cap_kw: override the scalar site power cap.
      - extra_sessions: inject additional Session objects into the day.

    Args:
        day: Original DaySessions.
        site: Original SiteConfig.
        tool_arguments: Parsed JSON arguments from the LLM tool call.

    Returns:
        (modified_day, modified_site) — originals are not mutated.
    """
    modified_day = day
    modified_site = site

    disabled = set(str(c) for c in tool_arguments.get("disabled_chargers") or [])
    extra_raw: List[Dict[str, Any]] = tool_arguments.get("extra_sessions") or []
    new_cap = tool_arguments.get("site_cap_kw")

    # Rebuild sessions if any charger is disabled or extra sessions are added.
    if disabled or extra_raw:
        new_sessions: List[Session] = []
        for sess in day.sessions:
            if sess.charger_id in disabled:
                # Replace with a zero-power clone — solver will assign 0 power.
                # We keep the session so indices stay consistent; unmet energy
                # will equal energy_kwh for this session.
                new_sessions.append(
                    Session(
                        session_id=sess.session_id,
                        arrival_idx=sess.arrival_idx,
                        departure_idx=sess.departure_idx,
                        energy_kwh=sess.energy_kwh,
                        charger_id=sess.charger_id,
                        max_power_kw=1e-9,  # effectively zero; must be > 0 for schema
                    )
                )
            else:
                new_sessions.append(sess)

        for k, raw in enumerate(extra_raw):
            new_sessions.append(
                Session(
                    session_id=f"extra-{k}",
                    arrival_idx=int(raw["arrival_idx"]),
                    departure_idx=int(raw["departure_idx"]),
                    energy_kwh=float(raw["energy_kwh"]),
                    charger_id=f"extra-{k}",
                    max_power_kw=float(raw["max_power_kw"]),
                )
            )

        modified_day = DaySessions(
            sessions=new_sessions,
            n_steps=day.n_steps,
            dt_hours=day.dt_hours,
        )

    if new_cap is not None:
        modified_site = copy.copy(site)
        modified_site.P_max_kw = float(new_cap)

    return modified_day, modified_site


def _execute_solve(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    tool_arguments: Dict[str, Any],
) -> tuple[SolveResult, Dict[str, Any], DaySessions, SiteConfig]:
    """Run the CVXPY solver and return the result with the problem it solved.

    Applies any what-if overrides (disabled_chargers, site_cap_kw, extra_sessions)
    before calling the solver. The tool_result_dict is a short JSON-serialisable
    summary for the LLM; the full schedule matrix is NOT included.

    Args:
        day: The base day of the request.
        site: The base site configuration of the request.
        tou: Tariff for the horizon.
        tool_arguments: Parsed JSON arguments from the LLM tool call.

    Returns:
        ``(solve_result, tool_result, effective_day, effective_site)``. The last
        two are the problem the solver actually read: with a what-if they differ
        from ``day`` and ``site``, and every later step that judges the schedule
        (the constraint check and the verification gate) must use them. Checking
        a what-if schedule against the base day compares it with a problem that
        was never solved: with ``extra_sessions`` the schedule has more rows than
        the day has sessions, and with ``site_cap_kw`` or ``disabled_chargers``
        the limits are the wrong ones.
    """
    penalty_unmet = float(tool_arguments.get("penalty_unmet", 1e6))
    effective_day, effective_site = _apply_what_if(day, site, tool_arguments)
    solve_result = optimize(effective_day, effective_site, tou, penalty_unmet=penalty_unmet)

    pct_served = float(
        pct_fully_served(solve_result.schedule, effective_day, effective_day.dt_hours)
    )
    total_unmet = float(np.sum(solve_result.unmet_energy_kwh))

    tool_result: Dict[str, Any] = {
        "success": solve_result.success,
        "total_cost_usd": round(solve_result.total_cost_usd, 4),
        "peak_load_kw": round(solve_result.peak_load_kw, 4),
        "total_unmet_kwh": round(total_unmet, 4),
        "pct_fully_served": round(pct_served, 2),
        "n_sessions": len(effective_day.sessions),
        "n_steps": effective_day.n_steps,
    }
    if solve_result.status is not None:
        tool_result["solver_status"] = solve_result.status
    if solve_result.inaccurate:
        # success collapses OPTIMAL and OPTIMAL_INACCURATE; say which this was
        # rather than let a reduced-accuracy solve look like a clean optimum.
        tool_result["solver_inaccurate"] = True
    if not solve_result.success and solve_result.message:
        tool_result["message"] = solve_result.message

    # Surface which what-if overrides were active so the LLM can reference them.
    what_if_notes: Dict[str, Any] = {}
    if tool_arguments.get("disabled_chargers"):
        what_if_notes["disabled_chargers"] = tool_arguments["disabled_chargers"]
    if tool_arguments.get("site_cap_kw") is not None:
        what_if_notes["site_cap_kw_override"] = tool_arguments["site_cap_kw"]
    if tool_arguments.get("extra_sessions"):
        what_if_notes["extra_sessions_added"] = len(tool_arguments["extra_sessions"])
    if what_if_notes:
        tool_result["what_if"] = what_if_notes

    return solve_result, tool_result, effective_day, effective_site


# ---------------------------------------------------------------------------
# System message (role + tool access; problem text comes from Phase B-style prompt)
# ---------------------------------------------------------------------------

def _build_system_message() -> str:
    """System message: role, conditional tool-use rules, and what-if guidance."""
    return methods.read_text("_shared/agent_system_prompt.txt")


# ---------------------------------------------------------------------------
# Gate bookkeeping
# ---------------------------------------------------------------------------

def _gate_payload(
    result: GateResult,
    *,
    action: str,
    attempts: int,
    declared_failure: bool,
) -> Dict[str, Any]:
    """Build the gate's per-condition row for the trace file.

    Args:
        result: The GateResult of the last verification pass.
        action: The gate's last action ("accept" | "retry" | "declare_failure").
        attempts: How many answers were verified (1 or 2).
        declared_failure: True when the declared-failure text was surfaced.

    Returns:
        ``GateResult.as_row()`` (one status and one residual per condition) plus
        the loop's own fields and each condition's plain-English detail.
    """
    payload: Dict[str, Any] = dict(result.as_row())
    payload["gate_action"] = action
    payload["gate_attempts"] = attempts
    payload["gate_declared_failure"] = declared_failure
    payload["conditions"] = {
        cond.name: {
            "label": cond.label,
            "status": cond.status,
            "residual": cond.residual,
            "detail": cond.detail,
        }
        for cond in result.conditions.values()
    }
    return payload


def _attach_gate_row(trace_path: Optional[Path], payload: Dict[str, Any]) -> None:
    """Store the gate row next to the run it judged, under the key ``gate``.

    The recorder owns the trace file, so the row is added to the JSON it just
    wrote. A row that cannot be added is a lost audit record, not a detail: it
    warns and falls back to a sibling ``<run_id>.gate.json`` rather than
    disappearing.

    Args:
        trace_path: Path the recorder wrote, or None when no trace was written.
        payload: The row from ``_gate_payload``.
    """
    if trace_path is None:
        return
    try:
        data = json.loads(Path(trace_path).read_text(encoding="utf-8"))
        data["gate"] = payload
        Path(trace_path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:  # pragma: no cover - only a broken/absent trace file
        sidecar = Path(trace_path).with_suffix(".gate.json")
        warnings.warn(
            f"could not attach the gate row to {trace_path} ({exc}); "
            f"writing it to {sidecar} instead",
            RuntimeWarning,
            stacklevel=2,
        )
        sidecar.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class AgentLLMResult:
    """Outcome of one agent run: schedule, metrics, explanation, gate, and cost.

    Iterating the object yields the six legacy values
    ``(schedule, total_cost_usd, peak_load_kw, unmet_energy_kwh, feasible,
    explanation)``, so callers that still unpack a tuple keep working while new
    callers read ``usage``, ``gate`` and ``trace_path`` by name.

    Attributes:
        schedule: Power schedule of shape (n_sessions, n_steps) in kW. Rows
            follow ``posed_day.sessions``, which a what-if can extend.
        total_cost_usd: Total energy cost in USD.
        peak_load_kw: Maximum total power draw across all sessions (kW).
        unmet_energy_kwh: Total unmet energy across all sessions (kWh).
        feasible: True if the schedule satisfies every constraint of the problem
            that was posed.
        explanation: Natural-language summary from the LLM, or the gate's
            declared-failure text when verification failed twice.
        usage: Prompt, completion, and total tokens, number of model calls,
            number of tool calls, and wall-clock seconds for this run.
        model: Resolved ``provider:model`` id that produced the run.
        trace_path: Path of the JSON trace written for this run, if any.
        tool_called: True if the solver tool was invoked at least once.
        gate: The verification gate's verdict, ready for
            ``evaluation.outcome.classify_outcome``. None when the model never
            called the solver, so there was no schedule to verify.
        gate_row: The gate's per-condition row, the same dict stored in the
            trace. Empty when the gate did not run.
        gate_attempts: Answers the gate verified: 0, 1, or 2.
        declared_failure: True when the gate declared the failure and this
            result carries the gate's text, a zero schedule, and no numbers.
        posed_day: The day actually solved, i.e. after any what-if override.
        posed_site: The site configuration actually solved.
        check_result: Constraint check of the schedule against the posed
            problem. None when the solver was never called.
        tool_outputs: Every solver tool output of the episode, oldest first, as
            the model saw them. A harness scoring traceability needs these.
    """

    schedule: np.ndarray
    total_cost_usd: float
    peak_load_kw: float
    unmet_energy_kwh: float
    feasible: bool
    explanation: str
    usage: RunUsage = field(default_factory=RunUsage)
    model: str = ""
    trace_path: Optional[Path] = None
    tool_called: bool = False
    gate: Optional[GateVerdict] = None
    gate_row: Dict[str, Any] = field(default_factory=dict)
    gate_attempts: int = 0
    declared_failure: bool = False
    posed_day: Optional[DaySessions] = None
    posed_site: Optional[SiteConfig] = None
    check_result: Optional[CheckResult] = None
    tool_outputs: List[Dict[str, Any]] = field(default_factory=list)

    def __iter__(self) -> Iterator[Any]:
        """Yield the legacy 6-tuple so existing unpacking callers still work."""
        return iter(
            (
                self.schedule,
                self.total_cost_usd,
                self.peak_load_kw,
                self.unmet_energy_kwh,
                self.feasible,
                self.explanation,
            )
        )


# ---------------------------------------------------------------------------
# Main LLM agent function
# ---------------------------------------------------------------------------

def run_agent_llm(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    request: str = "Minimize energy cost for this day.",
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    max_tool_rounds: int = 3,
    client: Optional[Any] = None,
    run_id: Optional[str] = None,
    trace_dir: Optional[Path] = None,
    write_trace: bool = True,
    gate: bool = True,
) -> AgentLLMResult:
    """Run the LLM agent with a CVXPY solver tool, behind the verification gate.

    ``gate=False`` is the ReAct row of the paper's table: the same loop, the
    same tool, the same round budget, and the first answer surfaced as written,
    with nothing checking it. It exists so that the difference between that row
    and the gated one is the gate and nothing else, which is the contrast the
    solver-grounded design is measured by. Everything before the gate is shared
    code, so the two rows cannot drift apart.

    Holds a multi-turn Chat Completions conversation. The LLM decides whether
    to call `solve_ev_schedule` based on the request type:

      - Scheduling / optimization requests → LLM calls the tool.
      - What-if requests → LLM calls the tool with constraint overrides
        (disabled_chargers, site_cap_kw, extra_sessions).
      - Qualitative / conceptual questions → LLM answers directly; tool is
        not called and the returned schedule is a zero matrix (feasible=False).

    Once there is an answer to surface, the gate runs:

      1. ``verify_answer`` on the answer, the schedule, and the tool outputs,
         all against the problem that was posed.
      2. ``decide`` with ``attempt=1``. On "accept" the answer is surfaced.
      3. On "retry" the gate's message is appended as a user turn and the model
         answers once more. A solver call in that turn is blocked when
         ``retry_changes_problem`` says it would change the problem.
      4. ``verify_answer`` and ``decide`` again with ``attempt=2``. On "accept"
         the second answer is surfaced; otherwise the gate's declared-failure
         text is returned verbatim with a zero schedule and no numbers.

    A run whose model never called the solver skips the gate: nothing
    solver-grounded was produced, so there is nothing to verify. ``gate`` is then
    None, which ``classify_outcome`` reads as "this arm had no gate on this day"
    and which can never be scored as an escalation.

    Every model call is timed and its usage accumulated, so the returned
    ``usage`` reports the whole run: tokens, model calls, tool calls, seconds.
    The transcript, the tool calls with their arguments and returned JSON, the
    final answer, and the gate's per-condition row are written to a JSON trace
    for auditing.

    Args:
        day: DaySessions with sessions and horizon.
        site: SiteConfig with power cap.
        tou: TOUConfig with TOU rates.
        request: Natural-language request for the agent.
        model: Model id as ``provider:model`` (e.g. ``openrouter:openai/gpt-4o``)
            or a bare id resolved against the default provider. Defaults to
            EV_LLM_MODEL, else ``openrouter:openai/gpt-4o``.
        api_key: Provider key; falls back to OPENROUTER_API_KEY or
            OPENAI_API_KEY depending on the resolved provider.
        max_tool_rounds: Maximum tool-call rounds before ending the loop.
        client: Pre-built client exposing ``chat.completions.create``. Used by
            tests; when given, no key is required and none is read.
        run_id: Identifier for the trace file, normally the day (e.g.
            "2019-06-15"). Defaults to a UTC timestamp.
        trace_dir: Root directory for traces; defaults to
            ``ev-scheduling/results/traces`` or ``EV_TRACE_DIR``.
        write_trace: Set False to skip writing the trace file.

    Returns:
        AgentLLMResult. It also unpacks as the legacy 6-tuple
        (schedule, total_cost_usd, peak_load_kw, unmet_energy_kwh, feasible,
        explanation).

    Raises:
        ValueError: If no API key is available for the resolved provider.
    """
    spec: ModelSpec = parse_model_spec(model)
    if client is None:
        client = build_client(spec, api_key=api_key)

    recorder = RunRecorder(spec=spec, arm="agent", run_id=run_id or "", request=request)

    # Input = natural-language problem description + user request. Tool access is
    # via the tools parameter; the LLM calls solve_ev_schedule when it needs to.
    user_content = build_prompt_for_agent(day, site, tou, request)

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _build_system_message()},
        {"role": "user", "content": user_content},
    ]

    last_solve_result: Optional[SolveResult] = None
    # The problem the last solve actually read: a what-if changes it, and every
    # later judgement has to use it rather than the untouched request.
    posed_day: DaySessions = day
    posed_site: SiteConfig = site
    tool_outputs: List[Dict[str, Any]] = []
    first_solve_arguments: Optional[Dict[str, Any]] = None

    def _talk(tool_budget: int, *, block_problem_changes: bool) -> Optional[str]:
        """Let the model talk until it stops calling tools; return its final text.

        Args:
            tool_budget: Tool calls allowed in this phase.
            block_problem_changes: True during the retry, where a call that
                changes the problem is refused instead of solved.

        Returns:
            The model's final text turn. None when it never wrote one, which is
            not the same as the empty string: a model that wrote an empty answer
            has had its turn, and asking again would be a second one.
        """
        nonlocal last_solve_result, posed_day, posed_site, first_solve_arguments
        used = 0
        text: Optional[str] = None
        while used < tool_budget:
            response = call_chat(
                client,
                recorder,
                with_tools=True,
                model=spec.model,
                messages=messages,
                tools=[_SOLVE_TOOL],
                tool_choice="auto",
                temperature=0.0,
            )
            choice = response.choices[0]
            assistant_msg = choice.message

            # Append the assistant turn (including tool_calls if present).
            messages.append(assistant_msg.model_dump(exclude_none=True))

            if not assistant_msg.tool_calls:
                # Final text turn — capture explanation and stop.
                text = (assistant_msg.content or "").strip()
                break

            # Process every tool call in this turn.
            for tc in assistant_msg.tool_calls:
                used += 1
                if tc.function.name != "solve_ev_schedule":
                    # Unknown tool — return empty result so the conversation can continue.
                    unknown = {"error": f"Unknown tool: {tc.function.name}"}
                    recorder.record_tool_call(
                        call_id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                        output=unknown,
                        latency_s=0.0,
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(unknown),
                    })
                    continue

                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                if block_problem_changes and retry_changes_problem(
                    args, original_arguments=first_solve_arguments
                ):
                    blocked = {"error": BLOCKED_RETRY_ERROR, "blocked_arguments": args}
                    recorder.record_tool_call(
                        call_id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                        output=blocked,
                        latency_s=0.0,
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(blocked),
                    })
                    continue

                t_tool = time.time()
                solve_result, tool_result, effective_day, effective_site = _execute_solve(
                    day, site, tou, args
                )
                last_solve_result = solve_result
                posed_day, posed_site = effective_day, effective_site
                tool_outputs.append(tool_result)
                if first_solve_arguments is None:
                    first_solve_arguments = args

                recorder.record_tool_call(
                    call_id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                    output=tool_result,
                    latency_s=time.time() - t_tool,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result),
                })
        return text

    def _text_turn() -> str:
        """One model call with no tools, for the answer the tool loop never wrote."""
        response = call_chat(
            client,
            recorder,
            model=spec.model,
            messages=messages,
            temperature=0.0,
        )
        text = (response.choices[0].message.content or "").strip()
        if text:
            messages.append({"role": "assistant", "content": text})
        return text

    explanation = _talk(max_tool_rounds, block_problem_changes=False) or ""

    # If LLM stopped without a text turn, do one more call for the explanation.
    if not explanation and last_solve_result is not None:
        explanation = _text_turn()

    # If the LLM never called the tool there is no schedule — do not silently
    # run the solver. Return a zero schedule so the caller knows the tool was
    # not invoked and the result is not an optimised plan.
    if last_solve_result is None:
        n_sessions = len(day.sessions)
        schedule = np.zeros((n_sessions, day.n_steps), dtype=float)
        usage = recorder.finish(
            messages=messages, final_text=explanation, status="no_tool_call"
        )
        trace_path = recorder.write(trace_dir) if write_trace else None
        return AgentLLMResult(
            schedule=schedule,
            total_cost_usd=0.0,
            peak_load_kw=0.0,
            unmet_energy_kwh=float(sum(s.energy_kwh for s in day.sessions)),
            feasible=False,
            explanation=explanation,
            usage=usage,
            model=spec.key,
            trace_path=trace_path,
            tool_called=False,
            posed_day=day,
            posed_site=site,
        )

    def _verify(answer: str) -> tuple[GateResult, CheckResult]:
        """Run the five conditions on one answer, against the problem posed."""
        schedule = last_solve_result.schedule  # type: ignore[union-attr]
        checked = validate(schedule, posed_day, posed_site)
        prior_outputs, last_outputs = split_tool_outputs(tool_outputs)
        return (
            verify_answer(
                answer,
                solve_result=last_solve_result,
                day=posed_day,
                site=posed_site,
                tool_outputs=last_outputs,
                prior_tool_outputs=prior_outputs,
                request_text=request,
                tou=tou,
                check_result=checked,
            ),
            checked,
        )

    # Fallback answer: the solver's own numbers, stated by this module. It carries
    # no derived quantity (no saving against an uncontrolled baseline), because a
    # number no tool returned is exactly what the gate's E3 refuses.
    if not explanation:
        facts = extract_facts(
            last_solve_result.schedule,
            last_solve_result.total_cost_usd,
            last_solve_result.peak_load_kw,
            float(np.sum(last_solve_result.unmet_energy_kwh)),
        )
        explanation = generate_explanation(facts)

    if not gate:
        # ReAct without verification: the answer goes out as the model wrote it.
        # The schedule is checked against the problem posed only so that
        # ``feasible`` means the same thing it means on the gated path; nothing
        # is handed back to the model and nothing is declared.
        check_result = validate(last_solve_result.schedule, posed_day, posed_site)
        gate_row = {
            "gate_passed": None,
            "gate_action": "none",
            "gate_attempts": 0,
            "gate_declared_failure": False,
            "gate_reason": "no gate: the answer is surfaced as written",
        }
        usage = recorder.finish(messages=messages, final_text=explanation, status="ok")
        trace_path = recorder.write(trace_dir) if write_trace else None
        _attach_gate_row(trace_path, gate_row)
        return AgentLLMResult(
            schedule=last_solve_result.schedule,
            total_cost_usd=last_solve_result.total_cost_usd,
            peak_load_kw=last_solve_result.peak_load_kw,
            unmet_energy_kwh=float(np.sum(last_solve_result.unmet_energy_kwh)),
            feasible=check_result.feasible,
            explanation=explanation,
            usage=usage,
            model=spec.key,
            trace_path=trace_path,
            tool_called=True,
            gate=None,
            gate_row=gate_row,
            gate_attempts=0,
            declared_failure=False,
            posed_day=posed_day,
            posed_site=posed_site,
            check_result=check_result,
            tool_outputs=tool_outputs,
        )

    gate_result, check_result = _verify(explanation)
    decision = decide(gate_result, attempt=1)
    attempts = 1

    if decision.action == RETRY:
        messages.append({"role": "user", "content": decision.message})
        retry_text = _talk(RETRY_TOOL_BUDGET, block_problem_changes=True)
        if retry_text is None:
            # The model spent its turn on tool calls; ask once for the answer.
            retry_text = _text_turn()
        attempts = MAX_VERIFICATION_ATTEMPTS
        if retry_text:
            explanation = retry_text
            gate_result, check_result = _verify(explanation)
        # An empty second answer is not a second chance taken: the first verdict
        # stands and the gate declares the failure on it.
        decision = decide(gate_result, attempt=MAX_VERIFICATION_ATTEMPTS)

    declared = decision.action == DECLARE_FAILURE
    if declared:
        # Surface the gate's words and nothing else: no schedule, no numbers.
        explanation = decision.message
        schedule = np.zeros_like(last_solve_result.schedule)
        total_cost_usd = 0.0
        peak_load_kw = 0.0
        unmet_energy_kwh = 0.0
        feasible = False
    else:
        schedule = last_solve_result.schedule
        total_cost_usd = last_solve_result.total_cost_usd
        peak_load_kw = last_solve_result.peak_load_kw
        unmet_energy_kwh = float(np.sum(last_solve_result.unmet_energy_kwh))
        feasible = check_result.feasible

    gate_row = _gate_payload(
        gate_result, action=decision.action, attempts=attempts, declared_failure=declared
    )

    usage = recorder.finish(
        messages=messages,
        final_text=explanation,
        status="declared_failure" if declared else "ok",
    )
    trace_path = recorder.write(trace_dir) if write_trace else None
    _attach_gate_row(trace_path, gate_row)

    return AgentLLMResult(
        schedule=schedule,
        total_cost_usd=total_cost_usd,
        peak_load_kw=peak_load_kw,
        unmet_energy_kwh=unmet_energy_kwh,
        feasible=feasible,
        explanation=explanation,
        usage=usage,
        model=spec.key,
        trace_path=trace_path,
        tool_called=True,
        gate=decision.verdict,
        gate_row=gate_row,
        gate_attempts=attempts,
        declared_failure=declared,
        posed_day=posed_day,
        posed_site=posed_site,
        check_result=check_result,
        tool_outputs=tool_outputs,
    )


# ---------------------------------------------------------------------------
# Plan-and-Act (no gate)
# ---------------------------------------------------------------------------

def _plan_system_prompt() -> str:
    """The planner's fixed text plus the tool catalogue, rendered from the schema.

    The catalogue is generated from ``_SOLVE_TOOL`` so the planner sees exactly
    the arguments the executor accepts; a hand-written copy would drift.
    """
    fn = _SOLVE_TOOL["function"]
    props = fn.get("parameters", {}).get("properties", {})
    lines = [f"- {fn['name']}: {fn['description']}", "  arguments:"]
    for name, spec in props.items():
        lines.append(f"    {name} ({spec.get('type', 'any')}): {spec.get('description', '')}")
    return methods.read_text("plan_act_nogate/plan_system_prompt.txt") + "\n".join(lines)


def _parse_plan(text: str) -> List[Dict[str, Any]]:
    """The plan's steps out of the planner's reply, or an empty list.

    Accepts the JSON object as written, or fenced in a code block. Anything
    else is an empty plan, which the caller reports as such rather than
    guessing a call the model did not make.
    """
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):] if "{" in raw else raw
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return []
        try:
            payload = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return []
    steps = payload.get("plan") if isinstance(payload, dict) else None
    if not isinstance(steps, list):
        return []
    out: List[Dict[str, Any]] = []
    for step in steps:
        if isinstance(step, dict) and isinstance(step.get("tool"), str):
            args = step.get("args") if isinstance(step.get("args"), dict) else {}
            out.append({"tool": step["tool"], "args": args})
    return out


def run_agent_plan_act(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    request: str = "Minimize energy cost for this day.",
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    max_plan_steps: int = 3,
    client: Optional[Any] = None,
    run_id: Optional[str] = None,
    trace_dir: Optional[Path] = None,
    write_trace: bool = True,
) -> AgentLLMResult:
    """Plan-and-Act with no gate: plan every call at once, execute, then answer.

    Three model calls at most and no feedback between them: the planner emits
    the whole sequence of solver calls before any result exists, the executor
    runs them, and a final call writes the answer from the outputs. The row
    isolates solver access through a plan: it has the same tool and the same
    system prompt as the ReAct row, and differs from it in that the model never
    sees a tool result before committing to the next call.

    Args:
        day, site, tou: The problem as parsed.
        request: The user's request text.
        model, api_key, client: As for ``run_agent_llm``.
        max_plan_steps: Planned calls executed at most; the same round budget as
            the other agent rows.
        run_id, trace_dir, write_trace: Trace naming and placement.

    Returns:
        An ``AgentLLMResult`` with ``gate=None``: nothing verifies the answer.
    """
    spec: ModelSpec = parse_model_spec(model)
    if client is None:
        client = build_client(spec, api_key=api_key)
    recorder = RunRecorder(spec=spec, arm="plan_act", run_id=run_id or "", request=request)

    # -- plan: one call, no tools, no results to look at
    plan_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _plan_system_prompt()},
        {"role": "user", "content": request},
    ]
    response = call_chat(client, recorder, model=spec.model, messages=plan_messages, temperature=0.0)
    plan_text = (response.choices[0].message.content or "").strip()
    plan = _parse_plan(plan_text)[:max_plan_steps]

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _build_system_message()},
        {"role": "user", "content": request},
        {"role": "assistant", "content": plan_text},
    ]

    if not plan:
        usage = recorder.finish(messages=messages, final_text=plan_text, status="no_plan")
        trace_path = recorder.write(trace_dir) if write_trace else None
        return AgentLLMResult(
            schedule=np.zeros((len(day.sessions), day.n_steps), dtype=float),
            total_cost_usd=0.0,
            peak_load_kw=0.0,
            unmet_energy_kwh=float(sum(s.energy_kwh for s in day.sessions)),
            feasible=False,
            explanation=plan_text,
            usage=usage,
            model=spec.key,
            trace_path=trace_path,
            tool_called=False,
            posed_day=day,
            posed_site=site,
        )

    # -- act: every planned call, in order, with no model in the loop
    last_solve_result: Optional[SolveResult] = None
    posed_day, posed_site = day, site
    tool_outputs: List[Dict[str, Any]] = []
    for k, step in enumerate(plan, start=1):
        call_id = f"plan-{k}"
        if step["tool"] != "solve_ev_schedule":
            unknown = {"error": f"Unknown tool: {step['tool']}"}
            recorder.record_tool_call(call_id=call_id, name=step["tool"], arguments=step["args"], output=unknown, latency_s=0.0)
            messages.append({"role": "user", "content": f"Result of step {k} ({step['tool']}): {json.dumps(unknown)}"})
            continue
        t_tool = time.time()
        solve_result, tool_result, posed_day, posed_site = _execute_solve(day, site, tou, step["args"])
        last_solve_result = solve_result
        tool_outputs.append(tool_result)
        recorder.record_tool_call(
            call_id=call_id, name="solve_ev_schedule", arguments=step["args"], output=tool_result,
            latency_s=time.time() - t_tool,
        )
        messages.append({"role": "user", "content": f"Result of step {k} (solve_ev_schedule): {json.dumps(tool_result)}"})

    if last_solve_result is None:
        usage = recorder.finish(messages=messages, final_text=plan_text, status="no_tool_call")
        trace_path = recorder.write(trace_dir) if write_trace else None
        return AgentLLMResult(
            schedule=np.zeros((len(day.sessions), day.n_steps), dtype=float),
            total_cost_usd=0.0,
            peak_load_kw=0.0,
            unmet_energy_kwh=float(sum(s.energy_kwh for s in day.sessions)),
            feasible=False,
            explanation=plan_text,
            usage=usage,
            model=spec.key,
            trace_path=trace_path,
            tool_called=False,
            posed_day=day,
            posed_site=site,
        )

    # -- answer: one call, from the outputs, as written
    messages.append({"role": "user", "content": "Every planned step has run. Answer the request from the results above."})
    response = call_chat(client, recorder, model=spec.model, messages=messages, temperature=0.0)
    explanation = (response.choices[0].message.content or "").strip()
    if explanation:
        messages.append({"role": "assistant", "content": explanation})
    else:
        facts = extract_facts(
            last_solve_result.schedule,
            last_solve_result.total_cost_usd,
            last_solve_result.peak_load_kw,
            float(np.sum(last_solve_result.unmet_energy_kwh)),
        )
        explanation = generate_explanation(facts)

    check_result = validate(last_solve_result.schedule, posed_day, posed_site)
    gate_row = {
        "gate_passed": None,
        "gate_action": "none",
        "gate_attempts": 0,
        "gate_declared_failure": False,
        "gate_reason": "no gate: the answer is surfaced as written",
    }
    usage = recorder.finish(messages=messages, final_text=explanation, status="ok")
    trace_path = recorder.write(trace_dir) if write_trace else None
    _attach_gate_row(trace_path, gate_row)
    return AgentLLMResult(
        schedule=last_solve_result.schedule,
        total_cost_usd=last_solve_result.total_cost_usd,
        peak_load_kw=last_solve_result.peak_load_kw,
        unmet_energy_kwh=float(np.sum(last_solve_result.unmet_energy_kwh)),
        feasible=check_result.feasible,
        explanation=explanation,
        usage=usage,
        model=spec.key,
        trace_path=trace_path,
        tool_called=True,
        gate=None,
        gate_row=gate_row,
        gate_attempts=0,
        declared_failure=False,
        posed_day=posed_day,
        posed_site=posed_site,
        check_result=check_result,
        tool_outputs=tool_outputs,
    )
