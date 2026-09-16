"""llm/engine.py

LLM 调用核心引擎（意图解析 + Function Calling）。

目标（与 PRD 一致）：
- 单 LLM + tools（不引入 multi-agent / LangChain / LangGraph）
- 支持多轮 tool calling（一次用户输入可连续调用多个工具）
- 完整错误处理：API 失败、tool 失败、参数 JSON 解析失败等
- 会话历史管理：保留最近 N 条消息（默认约 20 轮对话）

本模块对 Streamlit 无依赖：
- 上层（app.py）可以把 st.session_state.session 传入这里
- tool 的执行通过 ToolDispatcher 注入

Revision R1 (reviewer-requested ablations)
------------------------------------------
``EngineConfig`` gained backward-compatible knobs so the *same* engine, tool set
and interaction budget can be run under different agent architectures:

* ``architecture``: ``"react"`` (default; thought -> tool calls -> observation,
  repeated up to ``max_tool_rounds``), ``"single_call"`` (one LLM call with
  tools, one tool round, one final LLM call without tools, no memory), or
  ``"plan_act"`` (one LLM call without tools that must emit a JSON plan, the
  plan is executed by the dispatcher with no LLM in between, one final LLM call
  writes the answer).
* ``max_rounds``: alias of the pre-existing ``max_tool_rounds`` cap (8 rounds,
  as reported in the paper). Either name may be passed; they are kept in sync.
* ``gate``: verification gate on tool payloads (see ``gate_verdict``).
* ``memory``: whether prior ``conversation_history`` is sent to the LLM.

``run()`` keeps its signature and behaviour; ``run_with_trace()`` additionally
returns a structured per-round trace (LLM content, tool calls, truncated tool
outputs, gate verdicts, token usage, wall-clock time).

Where the verification gate lives
---------------------------------
The numerical checks themselves are computed in the solver layer:
``solver/power_flow.py::run_power_flow`` (Newton-Raphson convergence; a
non-converged solve yields a ``PowerFlowResult`` with ``converged=False`` and no
numerical content) and ``solver/validators.py::validate_result`` (limit
annotation plus the system-level power-balance / KCL residual check, which
appends an advisory hint). The engine is the point where those payloads are
forwarded to the LLM, so the switchable *enforcement* is here: with
``gate=True`` (default) a non-converged payload that still carries numbers is
withheld (numerical fields blanked) before the LLM sees it — a no-op for real
PandaPower output, which is already blank — and with ``gate=False`` the payload
is forwarded verbatim. In both cases the verdict is recorded in the trace so
the ablation can count what the gate would have caught.
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from models.schemas import SessionState
from llm.prompts import SYSTEM_PROMPT
from llm.tools import TOOLS, ToolDispatcher, get_openai_tools

ARCHITECTURES = ("react", "single_call", "plan_act")

# Same tolerance as solver/validators.py::ValidationConfig.balance_tol_mw
GATE_BALANCE_TOL_MW = 0.01          # absolute floor, MW
GATE_BALANCE_REL_TOL = 1e-4         # relative to total load: 0.01 percent (case118 base case sits at 0.004 percent)

MAX_ROUNDS_EXCEEDED_TEXT = (
    "The tool-call round limit was reached before an answer could be verified. "
    "No numerical result is reported. Narrow the request or split it into fewer consecutive operations."
)
PLAN_UNPARSEABLE_TEXT = (
    "Plan formulation failed: the model did not return a parseable JSON plan, "
    "so no tools were executed and no numerical result is available."
)
GATE_WITHHELD_NOTE = (
    "Verification gate: the solver result did not pass verification, so numerical fields were "
    "withheld. Report the failure as stated in the gate reasons; do not describe the network as solved."
)


@dataclass(frozen=True)
class EngineConfig:
    """LLM 引擎配置。

    New fields (all defaults reproduce the pre-R1 behaviour exactly):

    architecture: "react" | "single_call" | "plan_act"
    max_rounds:   alias of ``max_tool_rounds`` (the ≤8-round cap used in the paper).
                  Pass either; ``__post_init__`` keeps both in sync.
    gate:         enforce the verification gate on tool payloads (default True).
    memory:       send prior conversation history to the LLM (default True).
                  ``single_call`` always behaves as ``memory=False``.
    trace_output_chars: truncation length for tool outputs stored in the trace.
    final_gate:   task-level verification V(x,c,z,y) applied once to the final answer
                  of the ``react`` architecture (see ``verify_final_answer``), instead
                  of (or in addition to) the in-loop observation ``gate``. On failure,
                  exactly one retry with the verdict appended to the conversation; a
                  second failure forces a declared-failure abstention. Default False.
    """

    model: str = "gpt-4o-mini"  # 默认值仅作为占位；实际运行可由 config.py/环境变量覆盖
    temperature: float = 0.2
    max_tool_rounds: int = 8
    max_history_messages: int = 40  # 约等于 20 轮（user+assistant）
    timeout_s: float = 60.0

    architecture: str = "react"
    max_rounds: Optional[int] = None
    gate: bool = True
    memory: bool = True
    trace_output_chars: int = 400
    final_gate: bool = False

    def __post_init__(self) -> None:
        if self.architecture not in ARCHITECTURES:
            raise ValueError(f"architecture must be one of {ARCHITECTURES}, got {self.architecture!r}")
        if self.max_rounds is None:
            object.__setattr__(self, "max_rounds", int(self.max_tool_rounds))
        else:
            object.__setattr__(self, "max_tool_rounds", int(self.max_rounds))


class LLMClient:
    """一个最小客户端接口：只要实现 create(...) 即可。

    生产环境可使用 OpenAI SDK 的适配器；测试环境可用 FakeClient。
    """

    def create(self, **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError


class OpenAIChatClient(LLMClient):
    """OpenAI Python SDK v1 适配器。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def create(self, **kwargs: Any) -> Any:
        return self._client.chat.completions.create(**kwargs)


def _trim_history(history: List[Dict[str, Any]], max_messages: int) -> List[Dict[str, Any]]:
    """保留最后 max_messages 条消息（不包含 system prompt）。"""
    if max_messages <= 0:
        return []
    if len(history) <= max_messages:
        return history
    return history[-max_messages:]


def _safe_json_loads(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s or "{}")
    except Exception:
        # OpenAI 有时会返回非严格 JSON（例如多余空格/换行仍 OK；但若真坏了就兜底）
        return {}


def _normalize_tool_calls(tool_calls: Any) -> List[Dict[str, Any]]:
    """把 tool_calls 规范化为 [{id,name,arguments}] 列表。"""
    if not tool_calls:
        return []

    norm: List[Dict[str, Any]] = []
    for tc in tool_calls:
        # SDK object
        if hasattr(tc, "id") and hasattr(tc, "function"):
            fn = tc.function
            norm.append(
                {
                    "id": getattr(tc, "id"),
                    "name": getattr(fn, "name", None),
                    "arguments": getattr(fn, "arguments", "{}"),
                }
            )
            continue

        # dict
        if isinstance(tc, dict):
            fn = tc.get("function", {})
            norm.append(
                {
                    "id": tc.get("id"),
                    "name": fn.get("name"),
                    "arguments": fn.get("arguments", "{}"),
                }
            )
            continue

    return norm


def _extract_choice_message(resp: Any) -> Dict[str, Any]:
    """从 OpenAI 响应中提取第一条 message，并转为 dict。"""
    # dict response
    if isinstance(resp, dict):
        msg = resp["choices"][0]["message"]
        return {
            "role": msg.get("role", "assistant"),
            "content": msg.get("content"),
            "tool_calls": _normalize_tool_calls(msg.get("tool_calls")),
        }

    # SDK response
    msg = resp.choices[0].message
    return {
        "role": getattr(msg, "role", "assistant"),
        "content": getattr(msg, "content", None),
        "tool_calls": _normalize_tool_calls(getattr(msg, "tool_calls", None)),
    }


def _extract_usage(resp: Any) -> Dict[str, Optional[int]]:
    """Return {prompt_tokens, completion_tokens} from a dict or SDK response (None if absent)."""
    usage = resp.get("usage") if isinstance(resp, dict) else getattr(resp, "usage", None)

    def _read(name: str) -> Optional[int]:
        if usage is None:
            return None
        val = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        try:
            return int(val) if val is not None else None
        except Exception:
            return None

    return {"prompt_tokens": _read("prompt_tokens"), "completion_tokens": _read("completion_tokens")}


# ---------------------------------------------------------------------------
# Verification gate (verdict + enforcement on tool payloads)
# ---------------------------------------------------------------------------

_PF_NUMERIC_KEYS = ("bus_voltages", "line_flows", "voltage_violations", "thermal_violations")
_PF_TOTAL_KEYS = ("total_generation_mw", "total_load_mw", "total_loss_mw")


def _find_pf_payload(obj: Any) -> Optional[Dict[str, Any]]:
    """Locate a PowerFlowResult-shaped dict: top-level, or nested under 'result'."""
    if not isinstance(obj, dict):
        return None
    if "converged" in obj and any(k in obj for k in _PF_TOTAL_KEYS):
        return obj
    nested = obj.get("result")
    if isinstance(nested, dict) and "converged" in nested:
        return nested
    return None


def _is_finite_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def gate_verdict(tool_output: str) -> Optional[Dict[str, Any]]:
    """Compute the verification-gate verdict for one tool output.

    Returns None when the output is not a power-flow result (e.g. load_case,
    get_status, errors). Otherwise returns a dict with:
      converged, power_balance_ok, mismatch_mw, carries_numbers, passed, reasons
    where ``passed = converged and power_balance_ok``.
    """
    try:
        obj = json.loads(tool_output or "")
    except Exception:
        return None
    pf = _find_pf_payload(obj)
    if pf is None:
        return None

    converged = bool(pf.get("converged"))
    reasons: List[str] = []
    if not converged:
        reasons.append("not_converged")

    gen, load, loss = (pf.get(k) for k in _PF_TOTAL_KEYS)
    mismatch: Optional[float] = None
    balance_ok = True
    if all(_is_finite_number(v) for v in (gen, load, loss)):
        mismatch = abs(float(gen) - (float(load) + float(loss)))
        balance_ok = mismatch <= max(GATE_BALANCE_TOL_MW, GATE_BALANCE_REL_TOL * abs(float(load)))
    elif converged:
        balance_ok = False
        reasons.append("totals_missing_or_nan")
    if converged and mismatch is not None and not balance_ok:
        reasons.append("power_balance_mismatch")

    carries_numbers = any(bool(pf.get(k)) for k in _PF_NUMERIC_KEYS) or any(
        _is_finite_number(pf.get(k)) and float(pf.get(k)) != 0.0 for k in _PF_TOTAL_KEYS
    )

    # Topology / validity check (added in revision R1): a "converged" solve can still leave
    # buses without a valid voltage, typically because a line outage isolated them. PandaPower
    # reports NaN for those buses. Reporting "all voltages within limits" in that state is an
    # unverified claim, so the gate fails and names the buses.
    isolated: List[Any] = []
    for bv in pf.get("bus_voltages") or []:
        if isinstance(bv, dict) and not _is_finite_number(bv.get("vm_pu")):
            isolated.append(bv.get("bus_id"))
    topology_ok = not isolated
    if converged and isolated:
        reasons.append("isolated_or_unsolved_buses")

    return {
        "converged": converged,
        "power_balance_ok": bool(balance_ok),
        "mismatch_mw": mismatch,
        "topology_ok": bool(topology_ok),
        "isolated_buses": isolated,
        "carries_numbers": bool(carries_numbers),
        "passed": bool(converged and balance_ok and topology_ok),
        "reasons": reasons,
    }


def _finite_or_none(x: Any) -> Optional[float]:
    return float(x) if _is_finite_number(x) else None


def verify_final_answer(
    trace: Dict[str, Any],
    final_answer_text: str,
    *,
    request_text: Optional[str] = None,
    balance_tol_mw: float = GATE_BALANCE_TOL_MW,
    balance_rel_tol: float = GATE_BALANCE_REL_TOL,
) -> Dict[str, Any]:
    """Task-level verification V(x, c, z, y), applied once to the final answer text.

    Five conditions, all evaluated on the last ``run_powerflow``-shaped output at or
    after the last network mutation (or the last such output in the whole trace, when
    no mutation happened): converged, active-power balance, no isolated buses,
    faithfulness of the answer's numbers, and currency (no stale pre-mutation numbers).
    ``passed`` requires all five. Only ``trace`` (the agent's own observed tool calls
    and outputs) and ``final_answer_text`` are used — never a reference solution.

    Conditions 1-3 (converged, balance, no_isolated_buses) read a single-state
    ``PowerFlowResult`` payload; requests answered from a different kind of tool
    output entirely (e.g. ``run_n1_contingency``'s ranking, which is not one network
    state) never produce one. When the trace carries no such payload anywhere, those
    three conditions do not apply to this item and are reported ``passed`` with
    ``"applicable": False`` rather than penalized as an unconverged solve.
    """
    from benchmarks import metrics as bm

    records = bm._tool_records_from_trace(trace)

    last_mut: Optional[int] = None
    for i, rec in enumerate(records):
        if str(rec.get("name") or "") == "load_case":
            last_mut = None
        elif bm._mutation_applied(rec):
            last_mut = i

    has_any_pf_payload = any(
        bm._find_pf_payload(bm._parse_output(rec.get("output"))) is not None for rec in records
    )

    resolve_idx: Optional[int] = None
    if has_any_pf_payload:
        search_from = last_mut if last_mut is not None else 0
        for i in range(len(records) - 1, search_from - 1, -1):
            if bm._is_resolve(records[i]):
                resolve_idx = i
                break

    pf: Optional[Dict[str, Any]] = None
    if resolve_idx is not None:
        pf = bm._find_pf_payload(bm._parse_output(records[resolve_idx].get("output")))

    conditions: Dict[str, Dict[str, Any]] = {}

    if not has_any_pf_payload:
        conditions["converged"] = {"passed": True, "residual": 0, "applicable": False}
        conditions["balance"] = {"passed": True, "residual": None, "applicable": False}
        conditions["no_isolated_buses"] = {"passed": True, "residual": 0, "applicable": False}
    else:
        converged = bool(pf.get("converged")) if pf is not None else False
        conditions["converged"] = {"passed": converged, "residual": 0 if converged else 1, "applicable": True}

        mismatch: Optional[float] = None
        balance_ok = False
        if pf is not None:
            gen, load, loss = (_finite_or_none(pf.get(k)) for k in _PF_TOTAL_KEYS)
            if gen is not None and load is not None and loss is not None:
                mismatch = abs(gen - (load + loss))
                balance_ok = mismatch <= max(balance_tol_mw, balance_rel_tol * abs(load))
        conditions["balance"] = {"passed": bool(balance_ok), "residual": mismatch, "applicable": True}

        isolated_buses: List[Any] = []
        if pf is not None:
            isolated_buses = [
                bv.get("bus_id") for bv in pf.get("bus_voltages") or [] if isinstance(bv, dict) and not _is_finite_number(bv.get("vm_pu"))
            ]
        conditions["no_isolated_buses"] = {
            "passed": not isolated_buses,
            "residual": len(isolated_buses),
            "applicable": True,
            "isolated_buses": isolated_buses,
        }

    tool_outputs = bm.tool_outputs_from_trace(trace)
    faith = bm.faithful_numbers(final_answer_text, tool_outputs, request_text=request_text)
    n_numbers = faith.get("n_numbers") or 0
    n_untraceable = faith.get("n_untraceable_numbers") or 0
    faith_residual = (n_untraceable / n_numbers) if n_numbers else 0.0
    conditions["faithfulness"] = {"passed": n_untraceable == 0, "residual": faith_residual}

    stale = bm.stale_state_check(trace, final_answer_text, request_text=request_text)
    if stale.get("stale_state_no_rerun"):
        currency_residual = int(stale.get("n_answer_numbers") or 0)
    else:
        currency_residual = int(stale.get("n_numbers_old_only") or 0)
    conditions["currency"] = {"passed": not bool(stale.get("stale_state")), "residual": currency_residual}

    last_mutation: Optional[Dict[str, Any]] = None
    if last_mut is not None:
        rec = records[last_mut]
        last_mutation = {"tool": rec.get("name"), "args": rec.get("arguments") or {}}

    return {"passed": all(c["passed"] for c in conditions.values()), "conditions": conditions, "last_mutation": last_mutation}


def _describe_mutation(mutation: Optional[Dict[str, Any]]) -> Optional[str]:
    """Plain-English description of the last network-changing tool call, for messages
    that must read like an explanation and not a log line."""
    if not mutation:
        return None
    tool, args = mutation.get("tool"), mutation.get("args") or {}
    if tool == "disconnect_line":
        return f"disconnecting the branch between bus {args.get('from_bus')} and bus {args.get('to_bus')}"
    if tool == "reconnect_line":
        return f"reconnecting the branch between bus {args.get('from_bus')} and bus {args.get('to_bus')}"
    if tool == "modify_load":
        return f"setting the load at bus {args.get('bus_id')} to {args.get('p_mw')} MW"
    if tool == "apply_remedial_action":
        return f"applying remedial action {args.get('action_index')}"
    return f"the last change ({tool})" if tool else None


def _condition_plain_text(name: str, cond: Dict[str, Any], verdict: Dict[str, Any], *, suggest_fix: bool = True) -> str:
    """Human-readable cause for one failed condition, naming buses/values instead of the
    internal condition key -- this is what ends up in the retry message and, if the retry
    also fails, in the user-facing abstention text.

    ``suggest_fix`` controls whether a corrective suggestion (e.g. "reconnect the branch")
    is appended. It must be False in the retry message: a model reading "reconnect the
    branch" as an instruction, rather than as commentary on a terminal abstention, will
    silently undo the very network change the request asked for (observed: given "disconnect
    the branch between bus 7 and bus 8", the retry called reconnect_line(7, 8) and reported
    the reconnected state as the answer -- formulation_check correctly flags this as
    extra_step, but verify_final_answer's own conditions can no longer tell, since the
    resulting state is genuinely converged and consistent). The suggestion is safe to keep
    in the abstention text, which is terminal (no further tool calls follow it).
    """
    mutation = verdict.get("last_mutation")
    mutation_desc = _describe_mutation(mutation)

    if name == "converged":
        return "the last power flow did not converge" + (f" after {mutation_desc}" if mutation_desc else "")

    if name == "balance":
        r = cond.get("residual")
        if _is_finite_number(r):
            return f"the last solution violates active-power balance by {r:.2f} MW"
        return "the last solution's power balance could not be checked (missing totals)"

    if name == "no_isolated_buses":
        buses = cond.get("isolated_buses") or []
        if not buses:
            return "one or more buses have no valid voltage, so the network is split"
        bus_txt = " and ".join(f"bus {b}" for b in buses)
        verb = "has" if len(buses) == 1 else "have"
        is_disconnect = bool(mutation) and mutation.get("tool") == "disconnect_line"
        cause = f" because {mutation_desc} isolated it from the slack bus" if is_disconnect else " and is isolated from the slack bus"
        text = f"{bus_txt} {verb} no valid voltage{cause}, so the network is split."
        if is_disconnect and suggest_fix:
            a = mutation.get("args") or {}
            text += f" Suggested next step: reconnect the branch between bus {a.get('from_bus')} and bus {a.get('to_bus')}, or analyse the connected part separately."
        return text

    if name == "faithfulness":
        r = cond.get("residual") or 0.0
        return f"{r:.0%} of the numbers in the answer do not match any tool output or the request"

    if name == "currency":
        r = cond.get("residual") or 0
        suffix = f" ({mutation_desc})" if mutation_desc else ""
        return f"the answer quotes {r} number(s) from a solve made before the last network change{suffix}"

    return name  # pragma: no cover - defensive, all five names are handled above


def _verification_retry_message(verdict: Dict[str, Any]) -> str:
    lines = ["Verification failed before this answer could be accepted. Failed condition(s):"]
    for name, cond in verdict["conditions"].items():
        if cond["passed"]:
            continue
        lines.append(f"- {_condition_plain_text(name, cond, verdict, suggest_fix=False)}")
    lines.append(
        "Produce a corrected final answer. You may call tools again if needed, but only to inspect the "
        "current state (e.g. re-running the power flow) -- do not undo or reverse a network change the "
        "request asked for (do not reconnect a line it asked you to disconnect, do not revert a load "
        "value it asked you to set) just to reach a state that passes verification. If the requested "
        "state genuinely fails, report that failure. Do not change a number without a tool call to "
        "support it."
    )
    return "\n".join(lines)


def _verification_abstention_text(verdict: Dict[str, Any]) -> str:
    failed = [(name, cond) for name, cond in verdict["conditions"].items() if not cond["passed"]]
    detail = " ".join(_condition_plain_text(name, cond, verdict).rstrip(".") + "." for name, cond in failed)
    return (
        "No numerical result is reported. Verification failed: "
        f"{detail} This is a declared failure of the verification step, not a claim that the network "
        "failed to converge."
    )


def _withhold_numbers(tool_output: str, verdict: Dict[str, Any]) -> str:
    """Blank the numerical fields of a non-converged payload (gate enforcement)."""
    obj = json.loads(tool_output)
    pf = _find_pf_payload(obj)
    assert pf is not None
    for k in _PF_NUMERIC_KEYS:
        if k in pf:
            pf[k] = []
    for k in _PF_TOTAL_KEYS:
        if k in pf:
            pf[k] = 0.0
    pf["converged"] = False
    gate_info: Dict[str, Any] = {"passed": False, "reasons": list(verdict.get("reasons", [])), "note": GATE_WITHHELD_NOTE}
    if verdict.get("isolated_buses"):
        gate_info["isolated_buses"] = list(verdict["isolated_buses"])
        gate_info["note"] = (
            GATE_WITHHELD_NOTE
            + f" The topology change split the network: buses {verdict['isolated_buses']} are isolated and have no "
            "valid solution. Tell the user the network is split (this is not a non-convergence) and do not report "
            "voltages or flows as valid."
        )
    pf["gate"] = gate_info
    return json.dumps(obj, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Plan-and-Act prompt + tolerant plan parser
# ---------------------------------------------------------------------------


def _tools_catalog_text() -> str:
    lines = []
    for t in TOOLS:
        props = t.get("parameters", {}).get("properties", {}) or {}
        req = t.get("parameters", {}).get("required", []) or []
        params = ", ".join(f"{k}: {v.get('type', 'any')}{'*' if k in req else ''}" for k, v in props.items()) or "(none)"
        lines.append(f"- {t['name']}({params}): {t.get('description', '')}")
    return "\n".join(lines)


PLAN_SYSTEM_PROMPT = (
    "You are the planner of a power-system analysis agent. You cannot call tools yourself. "
    "Given the user's request, output ONLY a JSON object of the form\n"
    '{"plan": [{"tool": "<tool_name>", "args": {...}}, ...]}\n'
    "listing, in execution order, every tool call needed to answer the request. "
    "Use only the tools below with exactly these argument names (* = required). "
    "Do not include explanations, markdown, or any text outside the JSON.\n\n"
    "Available tools:\n" + _tools_catalog_text()
)

FINAL_ANSWER_INSTRUCTION = (
    "Write the final answer for the user strictly from the tool outputs above. "
    "Never invent numbers; if a tool reported an error or a non-converged result, say so."
)


def _strip_code_fences(text: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else text.strip()


def parse_plan(text: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    """Tolerant parser for a Plan-and-Act plan.

    Accepts ``{"plan": [...]}``, ``{"steps": [...]}`` or a bare list, optionally
    wrapped in code fences or surrounded by prose. Each step needs a string
    ``tool``; ``args`` defaults to {}. Returns None if no valid plan is found.
    """
    if not text or not str(text).strip():
        return None
    raw = _strip_code_fences(str(text))

    candidates: List[str] = [raw]
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        i, j = raw.find(open_ch), raw.rfind(close_ch)
        if i != -1 and j > i:
            candidates.append(raw[i : j + 1])

    parsed: Any = None
    for cand in candidates:
        obj = _safe_json_loads(cand)
        if obj:
            parsed = obj
            break
    if parsed is None:
        return None

    steps: Any = parsed
    if isinstance(parsed, dict):
        steps = parsed.get("plan", parsed.get("steps"))
        if steps is None and isinstance(parsed.get("tool"), str):
            steps = [parsed]
    if not isinstance(steps, list) or not steps:
        return None

    plan: List[Dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("tool"), str) or not step["tool"].strip():
            return None
        args = step.get("args", step.get("arguments", {}))
        if isinstance(args, str):
            args = _safe_json_loads(args)
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return None
        plan.append({"tool": step["tool"].strip(), "args": args})
    return plan


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class _LLMCallError(Exception):
    def __init__(self, text: str):
        super().__init__(text)
        self.text = text


class LLMEngine:
    """单模型工具调用引擎。"""

    def __init__(
        self,
        client: LLMClient,
        dispatcher: ToolDispatcher,
        *,
        system_prompt: str = SYSTEM_PROMPT,
        config: EngineConfig = EngineConfig(),
    ):
        self.client = client
        self.dispatcher = dispatcher
        self.system_prompt = system_prompt
        self.config = config
        self._openai_tools = get_openai_tools()
        self.last_trace: Dict[str, Any] = {}

    # ------------------------------------------------------------------ public

    def run(self, user_message: str, session: SessionState) -> str:
        """处理一次用户输入，返回最终 assistant 文本。"""
        text, _ = self.run_with_trace(user_message, session)
        return text

    def run_with_trace(self, user_message: str, session: SessionState) -> Tuple[str, Dict[str, Any]]:
        """Same as run(), but also returns a structured trace dict.

        Trace keys: architecture, gate, memory, max_rounds, status, final_text,
        rounds (list; each has llm{content,tool_calls,usage,latency_s} and
        tools[{name,arguments,output,gate,enforced,latency_s}]), plan (plan_act),
        formulation_failure, n_llm_calls, n_tool_calls, n_tool_rounds,
        gate_checked, gate_failed, gate_enforced, prompt_tokens,
        completion_tokens, wall_time_s.
        """
        t0 = time.perf_counter()
        trace: Dict[str, Any] = {
            "architecture": self.config.architecture,
            "gate": bool(self.config.gate),
            "final_gate": bool(self.config.final_gate),
            "memory": bool(self.config.memory),
            "max_rounds": int(self.config.max_tool_rounds),
            "status": "ok",
            "final_text": "",
            "request_text": user_message,
            "rounds": [],
            "plan": None,
            "formulation_failure": False,
            "n_llm_calls": 0,
            "n_tool_calls": 0,
            "n_tool_rounds": 0,
            "gate_checked": 0,
            "gate_failed": 0,
            "gate_enforced": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "wall_time_s": 0.0,
            "verification": [],
            "verification_attempts": 0,
            "verification_outcome": None,
            "verification_retry_messages": [],
        }

        if session.conversation_history is None:
            session.conversation_history = []

        session.conversation_history = _trim_history(
            list(session.conversation_history), self.config.max_history_messages
        )

        # 组装 messages
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        use_memory = self.config.memory and self.config.architecture != "single_call"
        if use_memory:
            messages.extend(session.conversation_history)
        messages.append({"role": "user", "content": user_message})

        # 在 session 中记录 user
        session.conversation_history.append({"role": "user", "content": user_message})

        arch = self.config.architecture
        if arch == "react":
            text = self._run_react(messages, session, trace)
        elif arch == "single_call":
            text = self._run_single_call(messages, session, trace)
        else:
            text = self._run_plan_act(user_message, messages, session, trace)

        trace["final_text"] = text
        trace["wall_time_s"] = time.perf_counter() - t0
        self.last_trace = trace
        return text, trace

    # --------------------------------------------------------------- internals

    def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        *,
        with_tools: bool,
        trace: Dict[str, Any],
        round_rec: Dict[str, Any],
        system_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = dict(
            model=self.config.model,
            messages=messages if system_override is None else [{"role": "system", "content": system_override}] + messages[1:],
            temperature=self.config.temperature,
            timeout=self.config.timeout_s,
        )
        if with_tools:
            kwargs["tools"] = self._openai_tools
            kwargs["tool_choice"] = "auto"

        t0 = time.perf_counter()
        trace["n_llm_calls"] += 1
        try:
            resp = self.client.create(**kwargs)
        except Exception as e:
            round_rec["llm"] = {"error": f"{type(e).__name__}: {e}", "latency_s": time.perf_counter() - t0}
            raise _LLMCallError(f"LLM request failed: {type(e).__name__}: {e}")

        msg = _extract_choice_message(resp)
        usage = _extract_usage(resp)
        for k in ("prompt_tokens", "completion_tokens"):
            if usage.get(k) is not None:
                trace[k] += int(usage[k])
        round_rec["llm"] = {
            "content": msg.get("content"),
            "tool_calls": [{"id": tc["id"], "name": tc["name"], "arguments": tc["arguments"]} for tc in msg.get("tool_calls") or []],
            "usage": usage,
            "with_tools": with_tools,
            "latency_s": time.perf_counter() - t0,
        }
        return msg

    @staticmethod
    def _assistant_entry(msg: Dict[str, Any]) -> Dict[str, Any]:
        entry: Dict[str, Any] = {"role": "assistant", "content": msg.get("content")}
        # 若存在 tool_calls，需要把 tool_calls 也记录进 history（OpenAI 格式）
        if msg.get("tool_calls"):
            entry["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in msg["tool_calls"]
            ]
        return entry

    def _execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        session: SessionState,
        trace: Dict[str, Any],
        round_rec: Dict[str, Any],
    ) -> None:
        """Dispatch each tool call, apply the gate, append tool messages, record trace."""
        tools_rec: List[Dict[str, Any]] = round_rec.setdefault("tools", [])
        for tc in tool_calls:
            tool_name = tc.get("name")
            args_str = tc.get("arguments", "{}")
            args = _safe_json_loads(args_str) if isinstance(args_str, str) else dict(args_str or {})

            t0 = time.perf_counter()
            tool_output = self.dispatcher.dispatch(tool_name, args)
            latency = time.perf_counter() - t0
            trace["n_tool_calls"] += 1

            verdict = gate_verdict(tool_output)
            enforced = False
            if verdict is not None:
                trace["gate_checked"] += 1
                if not verdict["passed"]:
                    trace["gate_failed"] += 1
                # Enforce on ANY failed check (convergence, power balance, isolated buses), not only on
                # non-convergence: a converged solve with islanded buses must not reach the LLM as valid numbers.
                if self.config.gate and not verdict["passed"] and verdict["carries_numbers"]:
                    tool_output = _withhold_numbers(tool_output, verdict)
                    enforced = True
                    trace["gate_enforced"] += 1

            tools_rec.append(
                {
                    "id": tc.get("id"),
                    "name": tool_name,
                    "arguments": args,
                    "output": tool_output[: self.config.trace_output_chars],
                    "output_chars": len(tool_output),
                    "gate": verdict,
                    "enforced": enforced,
                    "latency_s": latency,
                }
            )

            tool_msg = {
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "name": tool_name,
                "content": tool_output,
            }
            session.conversation_history.append(tool_msg)
            messages.append(tool_msg)

    def _finish(self, text: str, session: SessionState, trace: Dict[str, Any], status: str) -> str:
        session.conversation_history.append({"role": "assistant", "content": text})
        trace["status"] = status
        return text

    # ---- react (identical to the pre-R1 loop) ---------------------------------

    def _run_react(self, messages: List[Dict[str, Any]], session: SessionState, trace: Dict[str, Any]) -> str:
        tool_round = 0
        verify_attempts = 0
        while True:
            if tool_round >= self.config.max_tool_rounds:
                return self._finish(MAX_ROUNDS_EXCEEDED_TEXT, session, trace, "max_rounds")

            round_rec: Dict[str, Any] = {"round": tool_round + 1}
            trace["rounds"].append(round_rec)
            try:
                msg = self._call_llm(messages, with_tools=True, trace=trace, round_rec=round_rec)
            except _LLMCallError as e:
                return self._finish(e.text, session, trace, "llm_error")

            assistant_entry = self._assistant_entry(msg)
            session.conversation_history.append(assistant_entry)
            messages.append(assistant_entry)

            tool_calls = msg.get("tool_calls") or []
            if tool_calls:
                self._execute_tool_calls(tool_calls, messages, session, trace, round_rec)
                tool_round += 1
                trace["n_tool_rounds"] = tool_round
                continue

            final_text = (msg.get("content") or "").strip()
            if not self.config.final_gate:
                trace["status"] = "ok"
                return final_text

            verify_attempts += 1
            verdict = verify_final_answer(trace, final_text, request_text=trace.get("request_text"))
            trace["verification"].append(verdict)
            if verdict["passed"]:
                trace["verification_attempts"] = verify_attempts
                trace["verification_outcome"] = "pass_first" if verify_attempts == 1 else "pass_retry"
                trace["status"] = "ok"
                return final_text

            if verify_attempts >= 2:
                trace["verification_attempts"] = verify_attempts
                trace["verification_outcome"] = "abstained"
                return self._finish(_verification_abstention_text(verdict), session, trace, "verification_failed")

            retry_msg = _verification_retry_message(verdict)
            trace["verification_retry_messages"].append(retry_msg)
            session.conversation_history.append({"role": "user", "content": retry_msg})
            messages.append({"role": "user", "content": retry_msg})

    # ---- single_call ------------------------------------------------------------

    def _run_single_call(self, messages: List[Dict[str, Any]], session: SessionState, trace: Dict[str, Any]) -> str:
        round_rec: Dict[str, Any] = {"round": 1}
        trace["rounds"].append(round_rec)
        try:
            msg = self._call_llm(messages, with_tools=True, trace=trace, round_rec=round_rec)
        except _LLMCallError as e:
            return self._finish(e.text, session, trace, "llm_error")

        assistant_entry = self._assistant_entry(msg)
        session.conversation_history.append(assistant_entry)
        messages.append(assistant_entry)

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            # The model answered directly; nothing to ground, no second call needed.
            trace["status"] = "ok"
            return (msg.get("content") or "").strip()

        self._execute_tool_calls(tool_calls, messages, session, trace, round_rec)
        trace["n_tool_rounds"] = 1

        # Exactly one final call, without tool definitions. Any tool_calls it
        # returns are ignored (no further tool rounds by construction).
        final_rec: Dict[str, Any] = {"round": 2, "final": True}
        trace["rounds"].append(final_rec)
        messages.append({"role": "user", "content": FINAL_ANSWER_INSTRUCTION})
        try:
            final_msg = self._call_llm(messages, with_tools=False, trace=trace, round_rec=final_rec)
        except _LLMCallError as e:
            return self._finish(e.text, session, trace, "llm_error")
        text = (final_msg.get("content") or "").strip()
        if not text:
            text = "The model returned no final answer text after the tool round."
            return self._finish(text, session, trace, "empty_final")
        return self._finish(text, session, trace, "ok")

    # ---- plan_act ---------------------------------------------------------------

    def _run_plan_act(
        self,
        user_message: str,
        messages: List[Dict[str, Any]],
        session: SessionState,
        trace: Dict[str, Any],
    ) -> str:
        # 1) Planning call: no tools, strict JSON plan.
        plan_rec: Dict[str, Any] = {"round": 1, "phase": "plan"}
        trace["rounds"].append(plan_rec)
        try:
            plan_msg = self._call_llm(
                messages, with_tools=False, trace=trace, round_rec=plan_rec, system_override=PLAN_SYSTEM_PROMPT
            )
        except _LLMCallError as e:
            return self._finish(e.text, session, trace, "llm_error")

        plan = parse_plan(plan_msg.get("content"))
        if plan is None:
            trace["formulation_failure"] = True
            trace["plan"] = None
            plan_rec["plan_raw"] = plan_msg.get("content")
            session.conversation_history.append({"role": "assistant", "content": plan_msg.get("content")})
            return self._finish(PLAN_UNPARSEABLE_TEXT, session, trace, "plan_unparseable")

        if len(plan) > self.config.max_tool_rounds:
            trace["plan_truncated"] = len(plan) - self.config.max_tool_rounds
            plan = plan[: self.config.max_tool_rounds]
        trace["plan"] = plan

        # 2) Act: execute the plan through the dispatcher, no LLM in between.
        #    Represented as one synthetic assistant tool_calls entry so the
        #    transcript stays valid OpenAI format for the final call.
        synthetic_calls = [
            {"id": f"plan_step_{i + 1}", "name": step["tool"], "arguments": json.dumps(step["args"], ensure_ascii=False)}
            for i, step in enumerate(plan)
        ]
        assistant_entry = self._assistant_entry({"content": plan_msg.get("content"), "tool_calls": synthetic_calls})
        session.conversation_history.append(assistant_entry)
        messages.append(assistant_entry)

        act_rec: Dict[str, Any] = {"round": 2, "phase": "act"}
        trace["rounds"].append(act_rec)
        self._execute_tool_calls(synthetic_calls, messages, session, trace, act_rec)
        trace["n_tool_rounds"] = 1

        # 3) Final call: write the answer from the outputs, no tools.
        final_rec: Dict[str, Any] = {"round": 3, "phase": "answer", "final": True}
        trace["rounds"].append(final_rec)
        messages.append({"role": "user", "content": FINAL_ANSWER_INSTRUCTION})
        try:
            final_msg = self._call_llm(messages, with_tools=False, trace=trace, round_rec=final_rec)
        except _LLMCallError as e:
            return self._finish(e.text, session, trace, "llm_error")
        text = (final_msg.get("content") or "").strip()
        if not text:
            text = "The model returned no final answer text after executing the plan."
            return self._finish(text, session, trace, "empty_final")
        return self._finish(text, session, trace, "ok")
