"""Trace figures: one PNG per run and one overview PNG per run directory.

Per run (``traces/NN_<request>.png``): the request, the steps as a colored timeline (LLM
calls, tool calls with their gate verdict, planner, final answer, verification), the
formulation check (intended against executed calls), the verification conditions, the
reporting checks, and a two-line narrative. Colors: blue LLM, teal tool, purple planner,
gold verification, green pass or solved, amber escalated, red fail or wrong.

Per directory (``overview.png``): one row per run, one cell per step, the outcome in the
last column, so the 40 runs of a method can be read at a glance.

matplotlib only, Agg backend, no LLM, no network.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch  # noqa: E402

C = {
    "llm": "#3B6FD4", "tool": "#2A9D8F", "planner": "#7B4FBF", "final": "#1F3A93", "verify": "#D9A404",
    "solved": "#2E9E5B", "escalated": "#E58F1A", "wrong": "#D63B3B", "error": "#7A7A7A", "other": "#9A9A9A",
    "pass": "#2E9E5B", "fail": "#D63B3B", "na": "#BDBDBD", "bg": "#FFFFFF", "panel": "#F5F6F8", "text": "#1B1F24", "muted": "#6B7280",
}
OUTCOME_LABEL = {"solved": "SOLVED AUTONOMOUSLY", "escalated": "ESCALATED TO A PERSON", "wrong_unflagged": "WRONG, UNFLAGGED", "error": "RUN ERROR", "other": "OTHER"}
OUTCOME_COLOR = {"solved": C["solved"], "escalated": C["escalated"], "wrong_unflagged": C["wrong"], "error": C["error"], "other": C["other"]}


# --------------------------------------------------------------------------- step extraction


def _fmt_call(name: str, args: Any, max_len: int = 34) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    if not args:
        s = f"{name}()"
    else:
        s = f"{name}(" + ", ".join(f"{k}={v}" for k, v in args.items()) + ")"
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def steps_of(payload: Dict[str, Any], row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten a trace into drawable steps: kind, label, sub (tokens), gate ('pass'|'fail'|None)."""
    tr = payload.get("trace") or {}
    steps: List[Dict[str, Any]] = []
    plan = tr.get("plan")
    if plan:
        steps.append({"kind": "planner", "label": f"plan: {len(plan)} step(s)", "sub": " → ".join(str(c.get("tool")) for c in plan)[:40], "gate": None})
    for rd in tr.get("rounds") or []:
        llm = rd.get("llm") if isinstance(rd.get("llm"), dict) else None
        if llm is not None:
            u = llm.get("usage") or {}
            sub = f"{u.get('prompt_tokens', '?')} in / {u.get('completion_tokens', '?')} out"
            calls = llm.get("tool_calls") or []
            if rd.get("final"):
                steps.append({"kind": "final", "label": "final answer", "sub": sub, "gate": None})
            elif calls:
                steps.append({"kind": "llm", "label": "LLM → " + ", ".join(str(c.get("name")) for c in calls)[:30], "sub": sub, "gate": None})
            else:
                steps.append({"kind": "llm", "label": "LLM text reply", "sub": sub, "gate": None})
        for tool in rd.get("tools") or []:
            gate = tool.get("gate")
            g = None if gate is None else ("pass" if (gate.get("passed") if isinstance(gate, dict) else gate) else "fail")
            out = tool.get("output")
            err = isinstance(out, str) and '"error"' in out[:200]
            steps.append({"kind": "tool", "label": _fmt_call(str(tool.get("name")), tool.get("arguments")), "sub": "tool error" if err else ("withheld" if tool.get("enforced") else ""), "gate": g})
    if not tr.get("rounds") and (payload.get("answer") or row.get("raw_response")):
        steps.append({"kind": "llm", "label": "LLM answered from the prompt", "sub": f"{row.get('prompt_tokens', '?')} in / {row.get('completion_tokens', '?')} out", "gate": None})
    ver = tr.get("verification") or []
    if ver:
        last = ver[-1]
        n_fail = sum(1 for c in (last.get("conditions") or {}).values() if not c.get("passed") and c.get("applicable") is not False)
        steps.append({"kind": "verify", "label": "verification gate", "sub": "all conditions pass" if last.get("passed") else f"{n_fail} condition(s) failed", "gate": "pass" if last.get("passed") else "fail"})
    return steps


def outcome_of(row: Dict[str, Any]) -> str:
    if row.get("escalated"):
        return "escalated"
    if row.get("wrong_silently"):
        return "wrong_unflagged"
    if row.get("solved_autonomously") or row.get("solved"):
        return "solved"
    if row.get("error"):
        return "error"
    return "other"


def narrative_lines(row: Dict[str, Any], steps: List[Dict[str, Any]]) -> List[str]:
    """Two or three plain sentences a reader can take away."""
    n_llm = sum(1 for s in steps if s["kind"] in ("llm", "final"))
    n_tool = sum(1 for s in steps if s["kind"] == "tool")
    tools = [s["label"].split("(")[0] for s in steps if s["kind"] == "tool"]
    if n_tool:
        first = f"The method made {n_llm} LLM call(s) and {n_tool} tool call(s): " + ", ".join(dict.fromkeys(tools)) + "."
    else:
        first = "The method answered from the prompt alone, without calling any tool."
    fe = row.get("formulation_exact")
    if fe is None:
        second = "No tool calls, so there is no formulation to check; every reported number is the model's own arithmetic."
    elif fe and row.get("declared_formulation") is not None:
        second = "The operations the model declared match the request exactly; the numbers are still its own arithmetic."
    elif fe:
        second = "The executed calls match the request exactly."
    else:
        second = f"Formulation not exact ({row.get('formulation_error_type')}): {row.get('formulation_detail') or ''}".rstrip(": ")
    oc = outcome_of(row)
    if oc == "solved":
        third = "Numbers match the solver reference and the answer was given autonomously."
    elif oc == "escalated":
        third = f"The method declared it could not answer (detected via {row.get('failure_detection_path')}), so the request goes to a person."
    elif oc == "wrong_unflagged":
        nun = row.get("n_untraceable_numbers")
        third = "The answer reports numbers that do not match the reference and does not say so" + (f"; {nun} of {row.get('n_numbers')} numbers trace to no tool output." if nun else ".")
    else:
        third = f"Run ended with an error: {str(row.get('error'))[:80]}" if row.get("error") else "Outcome could not be classified."
    return [first, second, third]


# --------------------------------------------------------------------------- per-run figure


def _wrap(s: str, width: int) -> str:
    return "\n".join(textwrap.wrap(str(s), width=width)) or ""


def _clip(s: str, n: int) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def render_run_figure(nn: int, row: Dict[str, Any], payload: Dict[str, Any], header: Dict[str, Any], out_png: Path) -> None:
    steps = steps_of(payload, row)
    oc = outcome_of(row)
    tr = payload.get("trace") or {}
    per_row = 6
    n_rows = max(1, (len(steps) + per_row - 1) // per_row)
    # vertical budget in inches, top to bottom
    H_HEAD, H_ROW, H_GAP, H_PANEL, H_NARR, H_LEG = 1.45, 1.15, 0.25, 1.95, 0.95, 0.35
    fig_h = H_HEAD + n_rows * H_ROW + H_GAP + H_PANEL + H_GAP + H_NARR + H_LEG
    fig_w = 14.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=90)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])

    def Y(inches_from_top: float) -> float:
        return 100.0 - 100.0 * inches_from_top / fig_h

    def H(inches: float) -> float:
        return 100.0 * inches / fig_h

    model = header.get("model_short") or str(row.get("model", "")).split("/")[-1]
    ax.text(1, Y(0.12), f"RUN {nn:02d}   {row.get('request_id')}   ·   {row.get('method')}   ·   {model}   ·   {row.get('case_name')}   ·   {row.get('difficulty')}", fontsize=12, weight="bold", color=C["text"], va="top")
    ax.add_patch(FancyBboxPatch((74, Y(0.95)), 25, H(0.42), boxstyle="round,pad=0.2,rounding_size=1.2", fc=OUTCOME_COLOR[oc], ec="none"))
    ax.text(86.5, Y(0.95) + H(0.21), OUTCOME_LABEL[oc], ha="center", va="center", fontsize=10.5, weight="bold", color="white")
    ax.text(1, Y(0.5), "Request: " + _wrap(row.get("request_text") or "", 105), fontsize=10.5, color=C["text"], va="top")

    # timeline
    box_w, gap = 15.0, 1.6
    box_h = H(0.78)
    for i, s in enumerate(steps):
        r, c = divmod(i, per_row)
        x = 1 + c * (box_w + gap)
        y = Y(H_HEAD + r * H_ROW) - box_h
        color = C[s["kind"]]
        ec = C["pass"] if s["gate"] == "pass" else (C["fail"] if s["gate"] == "fail" else color)
        ax.add_patch(FancyBboxPatch((x, y), box_w, box_h, boxstyle="round,pad=0.1,rounding_size=0.8", fc=color, ec=ec, lw=2.8 if s["gate"] else 1.0, alpha=0.96))
        ax.text(x + 0.6, y + box_h - H(0.08), f"{i + 1}. {_clip(s["label"], 21)}", fontsize=8.4, color="white", va="top", weight="bold")
        if s["sub"]:
            ax.text(x + 0.6, y + H(0.08), _clip(s["sub"], 24), fontsize=7.6, color="white", va="bottom")
        if s["gate"]:
            ax.text(x + box_w - 0.5, y + box_h - H(0.08), "✓" if s["gate"] == "pass" else "✗", fontsize=10, color="white", va="top", ha="right", weight="bold")
        if i + 1 < len(steps) and c < per_row - 1:
            ax.annotate("", xy=(x + box_w + gap - 0.15, y + box_h / 2), xytext=(x + box_w + 0.15, y + box_h / 2), arrowprops=dict(arrowstyle="->", color=C["muted"], lw=1.0))
    if not steps:
        ax.text(1, Y(H_HEAD) - box_h / 2, "no steps recorded in the trace", fontsize=9, color=C["muted"], va="center")

    # panels
    y_panel_top = Y(H_HEAD + n_rows * H_ROW + H_GAP)
    panel_h = H(H_PANEL)
    y_panel = y_panel_top - panel_h
    for x0, w in ((1, 48), (51, 48)):
        ax.add_patch(FancyBboxPatch((x0, y_panel), w, panel_h, boxstyle="round,pad=0.1,rounding_size=0.8", fc=C["panel"], ec="#E1E4E8"))
    intended = payload.get("intended_calls") or row.get("intended_calls") or []
    executed = payload.get("executed_calls") or row.get("executed_calls") or []
    declared = row.get("declared_formulation")
    exec_label = "executed: "
    if declared is not None or (not executed and row.get("formulation_exact") is not None):
        executed, exec_label = (declared or []), "declared: "
    fe = row.get("formulation_exact")
    fcol = C["na"] if fe is None else (C["pass"] if fe else C["fail"])
    ftxt = "n/a (no tools)" if fe is None else ("EXACT" if fe else f"NOT EXACT: {row.get('formulation_error_type')}")
    ax.text(2, y_panel_top - H(0.1), "FORMULATION", fontsize=9.5, weight="bold", color=C["text"], va="top")
    ax.text(14.5, y_panel_top - H(0.1), ftxt, fontsize=9.5, weight="bold", color=fcol, va="top")
    ax.text(2, y_panel_top - H(0.42), "intended: " + _wrap(" → ".join(_fmt_call(str(c.get("tool")), c.get("args"), 60) for c in intended) or "(none)", 76), fontsize=7.8, color=C["text"], va="top", family="monospace")
    ax.text(2, y_panel_top - H(0.95), exec_label + _wrap(" → ".join(_fmt_call(str(c.get("tool")), c.get("args"), 60) for c in executed) or "(none)", 76), fontsize=7.8, color=C["text"], va="top", family="monospace")

    ax.text(52, y_panel_top - H(0.1), "VERIFICATION", fontsize=9.5, weight="bold", color=C["text"], va="top")
    ver = tr.get("verification") or []
    x = 64.5
    if ver:
        for key, c in (ver[-1].get("conditions") or {}).items():
            st = "pass" if c.get("passed") else ("na" if c.get("applicable") is False else "fail")
            ax.add_patch(FancyBboxPatch((x, y_panel_top - H(0.36)), 4.2, H(0.26), boxstyle="round,pad=0.05,rounding_size=0.5", fc=C[st], ec="none"))
            ax.text(x + 2.1, y_panel_top - H(0.23), c.get("label", key[:3]), ha="center", va="center", fontsize=8, color="white", weight="bold")
            x += 4.8
    else:
        ax.text(64.5, y_panel_top - H(0.1), "not run by this method; V-pass checked offline: " + _yn(row.get("v_pass")), fontsize=8.3, color=C["muted"], va="top")
    rep = [
        f"numbers in answer {row.get('n_numbers', 'n/a')}, untraceable {row.get('n_untraceable_numbers', 'n/a')}  →  traceable answer: {_yn(row.get('faithful_answers'))}",
        f"V-pass (offline): {_yn(row.get('v_pass'))}    stale state quoted: {_yn(row.get('stale_state'))}    solved (computation right): {_yn(row.get('solved'))}" + (f"  [{row.get('solved_reason')}]" if row.get("solved_reason") else ""),
    ]
    m = row.get("metrics") or {}
    if m:
        rep.append(f"vs reference: voltage MAE {_g(m.get('voltage_mae'))} p.u., flow MAE {_g(m.get('flow_mae'))} MW, KCL mismatch {_g(m.get('kcl_mean_mismatch_mw'))} MW")
    rep.append(f"{row.get('n_llm_calls', 0)} LLM calls, {row.get('n_tool_calls', 0)} tool calls, {row.get('prompt_tokens', '?')} in / {row.get('completion_tokens', '?')} out tokens, {_g(row.get('wall_time_s'), 1)} s" + (f", ${float(row['cost_usd']):.4f}" if row.get("cost_usd") is not None else ""))
    ax.text(52, y_panel_top - H(0.5), "\n".join(rep), fontsize=7.9, color=C["text"], va="top", linespacing=1.45)

    # narrative
    ax.text(1, y_panel - H(H_GAP), "\n".join(_wrap(l, 150) for l in narrative_lines(row, steps)), fontsize=9.2, color=C["text"], va="top", linespacing=1.4)

    handles = [Patch(fc=C["llm"], label="LLM call"), Patch(fc=C["tool"], label="tool call"), Patch(fc=C["planner"], label="planner"), Patch(fc=C["final"], label="final answer"), Patch(fc=C["verify"], label="verification"), Patch(fc="white", ec=C["pass"], lw=2.4, label="gate pass (✓)"), Patch(fc="white", ec=C["fail"], lw=2.4, label="gate fail (✗)")]
    ax.legend(handles=handles, loc="lower right", ncol=7, fontsize=7.6, frameon=False, bbox_to_anchor=(1.0, 0.0))
    fig.savefig(out_png, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)


def _yn(v: Any) -> str:
    return "n/a" if v is None else ("yes" if v else "no")


def _g(v: Any, d: int = 4) -> str:
    if v is None:
        return "n/a"
    try:
        f = float(v)
    except Exception:
        return str(v)
    if f == 0:
        return "0"
    return f"{f:.2e}" if abs(f) < 1e-3 else f"{f:.{d}f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------- overview


def render_overview(rows: List[Dict[str, Any]], payloads: List[Dict[str, Any]], header: Dict[str, Any], out_png: Path, names: Optional[List[str]] = None) -> None:
    all_steps = [steps_of(p, r) for r, p in zip(rows, payloads)]
    max_steps = max((len(s) for s in all_steps), default=1)
    n = len(rows)
    cell_w, cell_h = 0.42, 0.26
    fig_w = 3.6 + cell_w * max_steps + 2.4
    fig_h = 1.6 + cell_h * n + 0.9
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=100)
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    model = header.get("model_short") or ""
    ax.text(0.1, fig_h - 0.25, f"{header.get('method')}  ·  {model}  ·  {header.get('case')}  ·  {n} runs  ·  {header.get('date', '')}", fontsize=11, weight="bold", va="top")
    counts = {k: sum(1 for r in rows if outcome_of(r) == k) for k in ("solved", "escalated", "wrong_unflagged")}
    ax.text(0.1, fig_h - 0.58, f"solved {counts['solved']}   escalated {counts['escalated']}   wrong unflagged {counts['wrong_unflagged']}      one row per request, one cell per step (numbered above); then formulation and where the request ended", fontsize=8.5, color=C["muted"], va="top")
    x0 = 3.5
    y_top = fig_h - 1.15
    for i, (r, steps) in enumerate(zip(rows, all_steps)):
        y = y_top - (i + 1) * cell_h
        rid = str(r.get('request_id'))
        num = rid.split('-')[-2] if rid.count('-') >= 2 else rid[-3:]
        label = f"{i + 1:02d}  {str(r.get('difficulty'))[:5]:5s} #{num}"
        ax.text(0.1, y + cell_h / 2, label, fontsize=6.8, va="center", family="monospace")
        for j, s in enumerate(steps):
            ec = C["pass"] if s["gate"] == "pass" else (C["fail"] if s["gate"] == "fail" else "white")
            ax.add_patch(plt.Rectangle((x0 + j * cell_w, y + 0.02), cell_w - 0.03, cell_h - 0.04, fc=C[s["kind"]], ec=ec, lw=1.4 if s["gate"] else 0.5))
        fe = r.get("formulation_exact")
        fx = x0 + max_steps * cell_w + 0.25
        ax.add_patch(plt.Rectangle((fx, y + 0.02), 0.5, cell_h - 0.04, fc=C["na"] if fe is None else (C["pass"] if fe else C["fail"]), ec="white", lw=0.5))
        ax.text(fx + 0.25, y + cell_h / 2, "form", fontsize=6, color="white", ha="center", va="center")
        oc = outcome_of(r)
        ax.add_patch(plt.Rectangle((fx + 0.6, y + 0.02), 1.6, cell_h - 0.04, fc=OUTCOME_COLOR[oc], ec="white", lw=0.5))
        ax.text(fx + 1.4, y + cell_h / 2, {"solved": "solved", "escalated": "escalated", "wrong_unflagged": "wrong, unflagged", "error": "error", "other": "other"}[oc], fontsize=6.6, color="white", ha="center", va="center", weight="bold")
    for j in range(max_steps):
        ax.text(x0 + j * cell_w + cell_w / 2, y_top + 0.05, str(j + 1), fontsize=6.5, ha="center", va="bottom", color=C["muted"])
    handles = [Patch(fc=C["llm"], label="LLM call"), Patch(fc=C["tool"], label="tool call"), Patch(fc=C["planner"], label="planner"), Patch(fc=C["final"], label="final answer"), Patch(fc=C["verify"], label="verification"), Patch(fc="white", ec=C["pass"], lw=1.8, label="gate pass"), Patch(fc="white", ec=C["fail"], lw=1.8, label="gate fail"), Patch(fc=C["solved"], label="solved"), Patch(fc=C["escalated"], label="escalated"), Patch(fc=C["wrong"], label="wrong, unflagged")]
    ax.legend(handles=handles, loc="lower left", ncol=5, fontsize=7, frameon=False, bbox_to_anchor=(0.0, -0.01))
    fig.savefig(out_png, bbox_inches="tight", facecolor="white")
    plt.close(fig)
