"""Build the LLM prompt: problem statement, constraints, and solution algorithm. No pre-solving."""

from typing import Optional, Sequence

import numpy as np

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions


def _format_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """Pipe-delimited Markdown table."""
    lines = [" | ".join(headers), " | ".join("---" for _ in headers)]
    lines += [" | ".join(str(v) for v in row) for row in rows]
    return "\n".join(lines)


def _peak_window_str(tou: TOUConfig) -> str:
    """Short note on expensive steps for cost-aware section."""
    rates = np.asarray(tou.rates_per_kwh).flatten()
    if rates.size == 0 or abs(float(np.max(rates)) - float(np.min(rates))) < 1e-9:
        return ""
    threshold = float(np.min(rates)) + 0.9 * (float(np.max(rates)) - float(np.min(rates)))
    peak = np.where(rates >= threshold)[0]
    if peak.size == 0:
        return ""
    return f"steps {int(peak[0])}–{int(peak[-1])}"


def build_prompt(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    instruction: Optional[str] = None,
) -> str:
    """Assemble the baseline LLM prompt. The LLM solves the schedule from scratch."""
    n_sessions = len(day.sessions)
    n_steps = day.n_steps
    dt_hours = day.dt_hours

    cap_kw = float(site.P_max_kw) if np.isscalar(site.P_max_kw) else None
    peak_str = _peak_window_str(tou)

    lines: list[str] = []

    # -------------------------------------------------------------------------
    # 1. Output format first (so the model knows the exact shape before reasoning)
    # -------------------------------------------------------------------------
    lines.append("OUTPUT FORMAT (read this first):")
    lines.append("")
    lines.append(
        f"You must output exactly {n_sessions} lines. Line i is for session i (i = 0 to {n_sessions - 1})."
    )
    lines.append(
        f"Each line has the form: Session i: v0 v1 v2 ... v{n_steps - 1}"
    )
    lines.append(
        f"That is exactly {n_steps} space-separated decimal numbers: one for time step 0, one for step 1, "
        f"..., one for step {n_steps - 1}. No more, no fewer. "
        f"The k-th number is the power (kW) for that session at time step k."
    )
    lines.append("")
    lines.append(
        f"Before you finish, verify: every line has exactly {n_steps} numbers. "
        "Zeros are required outside each session's charging window; inside the window use positive power."
    )
    lines.append("")

    # -------------------------------------------------------------------------
    # 2. Goal and priorities
    # -------------------------------------------------------------------------
    min_served = max(0, int(round(0.70 * n_sessions)))
    lines.append("GOAL:")
    lines.append(
        f"  1. Fully serve as many sessions as possible (target ≥{min_served} of {n_sessions}). "
        "A session is fully served when total energy delivered = energy_kwh (sum of power × dt over its window)."
    )
    lines.append(
        "  2. Satisfy all constraints below. A schedule with delivered=0 for a session that could be charged is invalid."
    )
    if peak_str:
        lines.append(
            f"  3. After maximizing fully served: prefer cheaper time steps (avoid {peak_str} if possible)."
        )
    lines.append("")

    # -------------------------------------------------------------------------
    # 3. Constraints
    # -------------------------------------------------------------------------
    lines.append("CONSTRAINTS:")
    lines.append(
        f"  • For session i: power is 0 for t < arrival_idx and t >= departure_idx. "
        "Only steps in [arrival_idx, departure_idx) may have positive power."
    )
    lines.append(
        "  • 0 <= power <= max_power_kw for every (session, step)."
    )
    if cap_kw is not None:
        lines.append(
            f"  • At every time step t, the sum of power across all sessions <= {cap_kw:.2f} kW."
        )
    else:
        lines.append(
            "  • At every time step t, the sum of power across all sessions <= site cap (varies by t)."
        )
    lines.append(
        f"  • For each session, total energy (sum of power × {dt_hours:.4f} over all steps) must not exceed energy_kwh."
    )
    lines.append("")

    # -------------------------------------------------------------------------
    # 4. Parameters and session table
    # -------------------------------------------------------------------------
    lines.append(f"PARAMETERS: {n_steps} time steps; each step = {dt_hours:.4f} h; step 0 = midnight.")
    if cap_kw is not None:
        lines.append(f"Site power cap = {cap_kw:.2f} kW at every step.")
    lines.append("")
    lines.append(f"SESSIONS ({n_sessions}):")
    headers = ["idx", "arrival_idx", "departure_idx", "energy_kwh", "max_power_kw"]
    rows: list[list[object]] = []
    for i, sess in enumerate(day.sessions):
        rows.append([
            i,
            sess.arrival_idx,
            sess.departure_idx,
            f"{sess.energy_kwh:.3f}",
            f"{sess.max_power_kw:.3f}",
        ])
    lines.append(_format_table(headers, rows))
    lines.append("")

    # -------------------------------------------------------------------------
    # 5. Solution algorithm (clear steps so the model follows one procedure)
    # -------------------------------------------------------------------------
    lines.append("ALGORITHM (follow in order):")
    lines.append("")
    lines.append(
        "Step A — For each session i: Let window = departure_idx - arrival_idx. "
        f"Needed average power = energy_kwh / (window × {dt_hours:.4f}). "
        "If that exceeds max_power_kw, the session is infeasible: use max_power_kw in every step of its window. "
        "Otherwise, assign that average power to every step in [arrival_idx, departure_idx) and 0 elsewhere."
    )
    lines.append("")
    lines.append(
        "Step B — For each time step t: If the sum of power across sessions at t exceeds the site cap, "
        "multiply every session's power at t by (cap / sum) so the total equals the cap."
    )
    lines.append("")
    lines.append(
        "Step C — After Step B some sessions may be short of energy_kwh. For each such session, "
        "add power in its window (without exceeding max_power_kw or the cap at any t) until delivered = energy_kwh."
    )
    lines.append("")
    lines.append(
        "Step D — Write your output: exactly one line per session, each line with exactly "
        f"{n_steps} numbers (power at step 0, step 1, ..., step {n_steps - 1}). "
        "Use 4 decimal places (e.g. 3.2709). Session 0 first, then Session 1, ..., Session " + str(n_sessions - 1) + "."
    )
    lines.append("")

    # -------------------------------------------------------------------------
    # 6. Minimal example
    # -------------------------------------------------------------------------
    lines.append("EXAMPLE (6 steps, 2 sessions, cap 10 kW, dt=0.25 h):")
    lines.append("  Session 0: [1,4), energy=3 kWh, max=7 kW → need 3/(3×0.25)=4 kW at steps 1,2,3.")
    lines.append("  Session 1: [2,5), energy=2.5 kWh, max=6 kW → need 2.5/(3×0.25)≈3.33 kW at steps 2,3,4.")
    lines.append("  Output (exactly 6 values per line):")
    lines.append("  Session 0: 0.0000 4.0000 4.0000 4.0000 0.0000 0.0000")
    lines.append("  Session 1: 0.0000 0.0000 3.3333 3.3333 3.3333 0.0000")
    lines.append("")

    # -------------------------------------------------------------------------
    # 7. Final reminder
    # -------------------------------------------------------------------------
    if instruction:
        lines.append("CONTEXT:")
        lines.append(instruction)
        lines.append("")

    lines.append("Now produce your schedule. Output only the Session lines, no other text.")
    lines.append(
        f"Remember: {n_sessions} lines, each with exactly {n_steps} space-separated numbers."
    )

    return "\n".join(lines)


def build_prompt_for_agent(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    request: str = "Minimize energy cost for this day.",
) -> str:
    """Same structure as build_prompt (Phase B) but for the agent: no output format.

    Returns GOAL, CONSTRAINTS, PARAMETERS, SESSIONS table, and ALGORITHM steps A/B/C.
    Replaces 'Step D' and 'produce your schedule' with an instruction to call the
    solve_ev_schedule tool and then explain the results. Used by Phase C LLM agent.
    """
    n_sessions = len(day.sessions)
    n_steps = day.n_steps
    dt_hours = day.dt_hours

    cap_kw = float(site.P_max_kw) if np.isscalar(site.P_max_kw) else None
    peak_str = _peak_window_str(tou)

    lines: list[str] = []

    # --- Goal and priorities (same as Phase B) ---
    min_served = max(0, int(round(0.70 * n_sessions)))
    lines.append("GOAL:")
    lines.append(
        f"  1. Fully serve as many sessions as possible (target ≥{min_served} of {n_sessions}). "
        "A session is fully served when total energy delivered = energy_kwh (sum of power × dt over its window)."
    )
    lines.append(
        "  2. Satisfy all constraints below. A schedule with delivered=0 for a session that could be charged is invalid."
    )
    if peak_str:
        lines.append(
            f"  3. After maximizing fully served: prefer cheaper time steps (avoid {peak_str} if possible)."
        )
    lines.append("")

    # --- Constraints (same as Phase B) ---
    lines.append("CONSTRAINTS:")
    lines.append(
        "  • For session i: power is 0 for t < arrival_idx and t >= departure_idx. "
        "Only steps in [arrival_idx, departure_idx) may have positive power."
    )
    lines.append(
        "  • 0 <= power <= max_power_kw for every (session, step)."
    )
    if cap_kw is not None:
        lines.append(
            f"  • At every time step t, the sum of power across all sessions <= {cap_kw:.2f} kW."
        )
    else:
        lines.append(
            "  • At every time step t, the sum of power across all sessions <= site cap (varies by t)."
        )
    lines.append(
        f"  • For each session, total energy (sum of power × {dt_hours:.4f} over all steps) must not exceed energy_kwh."
    )
    lines.append("")

    # --- Parameters and session table (same as Phase B) ---
    lines.append(f"PARAMETERS: {n_steps} time steps; each step = {dt_hours:.4f} h; step 0 = midnight.")
    if cap_kw is not None:
        lines.append(f"Site power cap = {cap_kw:.2f} kW at every step.")
    lines.append("")
    lines.append(f"SESSIONS ({n_sessions}):")
    headers = ["idx", "arrival_idx", "departure_idx", "energy_kwh", "max_power_kw"]
    rows: list[list[object]] = []
    for i, sess in enumerate(day.sessions):
        rows.append([
            i,
            sess.arrival_idx,
            sess.departure_idx,
            f"{sess.energy_kwh:.3f}",
            f"{sess.max_power_kw:.3f}",
        ])
    lines.append(_format_table(headers, rows))
    lines.append("")

    # --- Algorithm context (same as Phase B steps A–C; no Step D / output format) ---
    lines.append("ALGORITHM (the solver you can call follows this logic):")
    lines.append("")
    lines.append(
        "Step A — For each session i: Let window = departure_idx - arrival_idx. "
        f"Needed average power = energy_kwh / (window × {dt_hours:.4f}). "
        "If that exceeds max_power_kw, the session is infeasible: use max_power_kw in every step of its window. "
        "Otherwise, assign that average power to every step in [arrival_idx, departure_idx) and 0 elsewhere."
    )
    lines.append("")
    lines.append(
        "Step B — For each time step t: If the sum of power across sessions at t exceeds the site cap, "
        "multiply every session's power at t by (cap / sum) so the total equals the cap."
    )
    lines.append("")
    lines.append(
        "Step C — After Step B some sessions may be short of energy_kwh. For each such session, "
        "add power in its window (without exceeding max_power_kw or the cap at any t) until delivered = energy_kwh."
    )
    lines.append("")

    # --- Available tool note (descriptive only — system prompt governs when to call) ---
    lines.append("AVAILABLE TOOL:")
    lines.append(
        "solve_ev_schedule — runs the CVXPY convex optimizer on the problem above and returns: "
        "total_cost_usd, peak_load_kw, total_unmet_kwh, pct_fully_served. "
        "Supports optional what-if overrides: disabled_chargers (list of charger IDs to take "
        "offline), site_cap_kw (override the site power cap), extra_sessions (additional EVs "
        "to inject). Populate these from the user's request when applicable."
    )
    lines.append("")
    lines.append(f"User request: {request}")

    return "\n".join(lines)

