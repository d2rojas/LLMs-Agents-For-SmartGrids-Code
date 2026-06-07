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
"""

import copy
import json
import os
from typing import Any, Dict, List, Optional

import numpy as np

from agent.explain.explain import extract_facts, generate_explanation
from agent.optimize.call_solver import optimize
from agent.validate.validate import validate
from baseline.prompt import build_prompt_for_agent
from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions, Session
from evaluation.metrics import charge_asap_schedule, pct_fully_served, total_cost
from optimization.solver import SolveResult


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
) -> tuple[SolveResult, Dict[str, Any]]:
    """Run the CVXPY solver and return (SolveResult, tool_result_dict).

    Applies any what-if overrides (disabled_chargers, site_cap_kw, extra_sessions)
    before calling the solver. The tool_result_dict is a short JSON-serialisable
    summary for the LLM; the full schedule matrix is NOT included.
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

    return solve_result, tool_result


# ---------------------------------------------------------------------------
# System message (role + tool access; problem text comes from Phase B-style prompt)
# ---------------------------------------------------------------------------

def _build_system_message() -> str:
    """System message: role, conditional tool-use rules, and what-if guidance."""
    return (
        "You are an expert EV charging scheduler. You have access to the tool "
        "`solve_ev_schedule` that runs a CVXPY convex optimizer.\n\n"
        "WHEN TO CALL THE TOOL:\n"
        "  • Call `solve_ev_schedule` when the user's request requires computing or "
        "optimizing a charging schedule — for example: minimizing energy cost, reducing "
        "peak load, checking feasibility, or exploring a what-if scenario (e.g. a charger "
        "offline, a lower site cap, or an extra EV arriving).\n"
        "  • Do NOT call the tool for general questions, definitions, or conceptual "
        "explanations (e.g. 'What is TOU pricing?', 'What does peak load shaving mean?', "
        "'Summarize the last schedule'). Answer those directly from your own knowledge.\n\n"
        "WHAT-IF SCENARIOS:\n"
        "  • If the user asks 'what if charger X is offline?', call the tool with "
        "`disabled_chargers` set to the relevant charger ID(s).\n"
        "  • If the user asks 'what if the site cap is Y kW?', call the tool with "
        "`site_cap_kw` set to Y.\n"
        "  • If the user asks 'what if another EV arrives?', call the tool with "
        "`extra_sessions` containing the session details.\n\n"
        "AFTER CALLING THE TOOL:\n"
        "  • Use the returned metrics (total_cost_usd, peak_load_kw, total_unmet_kwh, "
        "pct_fully_served) to explain the outcome in plain language.\n"
        "  • Only report numbers you actually received from the tool result.\n\n"
        "WITHOUT CALLING THE TOOL:\n"
        "  • Answer directly and concisely. Do not invent schedule metrics."
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
    model: str = "gpt-4o",
    api_key: Optional[str] = None,
    max_tool_rounds: int = 3,
) -> tuple[np.ndarray, float, float, float, bool, str]:
    """Run the LLM agent with a CVXPY solver tool.

    Holds a multi-turn Chat Completions conversation. The LLM decides whether
    to call `solve_ev_schedule` based on the request type:

      - Scheduling / optimization requests → LLM calls the tool.
      - What-if requests → LLM calls the tool with constraint overrides
        (disabled_chargers, site_cap_kw, extra_sessions).
      - Qualitative / conceptual questions → LLM answers directly; tool is
        not called and the returned schedule is a zero matrix (feasible=False).

    Args:
        day: DaySessions with sessions and horizon.
        site: SiteConfig with power cap.
        tou: TOUConfig with TOU rates.
        request: Natural-language request for the agent.
        model: OpenAI model name.
        api_key: OpenAI API key (falls back to OPENAI_API_KEY env var).
        max_tool_rounds: Maximum tool-call rounds before ending the loop.

    Returns:
        Tuple of (schedule, total_cost_usd, peak_load_kw, unmet_energy_kwh,
                  feasible, explanation).
    """
    
    key = api_key or os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Set it in .env or pass api_key to run_agent_llm."
        )

    try:
        from openai import OpenAI  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "The 'openai' package is not installed. "
            "Install it with 'pip install openai>=1.0.0'."
        ) from exc

    client = OpenAI(api_key=key)

    # Input = natural-language problem description + user request. Tool access is
    # via the tools parameter; the LLM calls solve_ev_schedule when it needs to.
    user_content = build_prompt_for_agent(day, site, tou, request)

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _build_system_message()},
        {"role": "user", "content": user_content},
    ]

    last_solve_result: Optional[SolveResult] = None
    explanation: str = ""
    tool_rounds = 0

    while tool_rounds < max_tool_rounds:
        response = client.chat.completions.create(
            model=model,
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
            explanation = (assistant_msg.content or "").strip()
            break

        # Process every tool call in this turn.
        for tc in assistant_msg.tool_calls:
            tool_rounds += 1
            if tc.function.name != "solve_ev_schedule":
                # Unknown tool — return empty result so the conversation can continue.
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps({"error": f"Unknown tool: {tc.function.name}"}),
                })
                continue

            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            solve_result, tool_result = _execute_solve(day, site, tou, args)
            last_solve_result = solve_result

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(tool_result),
            })

    # If LLM stopped without a text turn, do one more call for the explanation.
    if not explanation and last_solve_result is not None:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
        )
        explanation = (response.choices[0].message.content or "").strip()

    # If the LLM never called the tool there is no schedule — do not silently
    # run the solver. Return a zero schedule so the caller knows the tool was
    # not invoked and the result is not an optimised plan.
    if last_solve_result is None:
        n_sessions = len(day.sessions)
        schedule = np.zeros((n_sessions, day.n_steps), dtype=float)
        return schedule, 0.0, 0.0, float(sum(s.energy_kwh for s in day.sessions)), False, explanation

    schedule = last_solve_result.schedule
    check_result = validate(schedule, day, site)
    feasible = check_result.feasible

    total_cost_usd = last_solve_result.total_cost_usd
    peak_load_kw = last_solve_result.peak_load_kw
    unmet_energy_kwh = float(np.sum(last_solve_result.unmet_energy_kwh))

    # Fallback explanation: template from computed facts.
    if not explanation:
        site_p_max = site.get_P_max_at_step(0) if day.n_steps > 0 else 50.0
        uncontrolled = charge_asap_schedule(day, float(site_p_max))
        uc_cost = total_cost(uncontrolled, tou, day.dt_hours)
        facts = extract_facts(
            schedule, total_cost_usd, peak_load_kw, unmet_energy_kwh,
            uncontrolled_cost_usd=uc_cost,
        )
        explanation = generate_explanation(facts)

    return schedule, total_cost_usd, peak_load_kw, unmet_energy_kwh, feasible, explanation
