"""Run cross-model LLM benchmarks for power-flow estimation tasks.

This runner evaluates multiple models, methods, cases and seeds against the
PandaPower ground truth and records scientific metrics, formulation /
faithfulness metrics and API usage.

Revision R1
-----------
* Perturbation and seeds: every item loads the case, applies
  ``benchmarks.requests.perturb_network(net, seed=..., k=...)`` (loads and
  generator setpoints scaled by a factor in ``[1 - 0.1k, 1 + 0.1k]``), computes
  the PandaPower ground truth on that perturbed net and hands the *same*
  perturbed net to the method under test (the dispatcher's ``load_case`` is
  wrapped so the agent can never reach the unperturbed base case).
  ``--k 0 --seeds 1`` (seed 0, zero-width perturbation) reproduces the pre-R1
  base-case behaviour exactly.
* Request-driven evaluation (``--requests file.jsonl`` or ``--gen-requests N``):
  each ``benchmarks.requests.Request`` is one item with ``intended_calls`` and a
  ground truth obtained by executing those calls on the perturbed net.
* Methods (``--method``, repeatable; ``--task`` kept for backward compatibility):
  ``baseline_pf`` / ``blueprint_pf`` (legacy single-prompt LLM-only tasks),
  ``llm_only:<strategy>``, ``single_call:<strategy>`` for strategy in
  structured|few_shot|cot|rag, ``react``, ``react_nogate``, ``plan_act``,
  ``plan_act_nogate``, ``pfagent`` (react + gate + memory) and ``rule_based``
  (regex parser, no LLM). All agent methods share the tool set and ``--max-rounds``.
* Metrics per item (see ``benchmarks/metrics.py``): ``formulation_exact`` and
  ``formulation_error_type``, Tier I-III numbers vs the perturbed ground truth,
  ``faithful_numbers`` / ``n_untraceable_numbers``, ``safe_failure``,
  ``claimed_success_on_failure``, ``stale_state`` (``_no_rerun`` / ``_quoted_old``)
  and cost (LLM calls, tool calls, rounds, tokens,
  wall time, USD).

Cost estimation is pricing-table driven. Update PRICE_BOOK_USD_PER_1M or pass
--pricing-file with the rates you want to use before treating cost numbers as authoritative.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import re
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import GEMINI_API_KEY, GEMINI_MODEL, OPENAI_API_KEY, OPENAI_MODEL
from benchmarks import metrics as bm
from benchmarks import scoring as bs

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OUT_DIR = "benchmarks/results"
DEFAULT_MAX_ROUNDS = 8
DEFAULT_K = 1
# Tool outputs are kept in full while metrics are computed, then truncated in the report.
TRACE_OUTPUT_CHARS_FULL = 5_000_000
TRACE_OUTPUT_CHARS_REPORT = 400

DEFAULT_REQUEST_TEXT = (
    "Load {case_name} and run the AC power flow, then report the total load, "
    "total generation and total losses in MW."
)

CORE_SCOREBOARD_FIELDS = [
    "success_rate",
    "voltage_mae_mean",
    "flow_mae_mean",
    "loading_rmse_mean",
    "voltage_f1_mean",
    "thermal_f1_mean",
    "convergence_match_rate",
    "prompt_tokens_mean",
    "completion_tokens_mean",
    "total_tokens_mean",
    "cost_usd_mean",
    "cost_usd_total",
]

# New (R1) aggregate fields; appended after the core ones so old readers keep working.
EXTENDED_SCOREBOARD_FIELDS = [
    "n_items",
    "formulation_exact_rate",
    "formulation_exact_count",
    "formulation_exact_total",
    "faithful_numbers_mean",
    "n_untraceable_numbers_mean",
    "safe_failure_rate",
    "safe_failure_count",
    "safe_failure_total",
    "claimed_success_on_failure_rate",
    "claimed_success_on_failure_count",
    "claimed_success_on_failure_total",
    "stale_state_rate",
    "stale_state_count",
    "stale_state_total",
    "stale_state_no_rerun_rate",
    "stale_state_no_rerun_count",
    "stale_state_no_rerun_total",
    "stale_state_quoted_old_rate",
    "stale_state_quoted_old_count",
    "stale_state_quoted_old_total",
    "converged_rate",
    "convergence_match_count",
    "convergence_match_total",
    "kcl_mean_mismatch_mw_mean",
    "power_balance_error_mean",
    "n_llm_calls_mean",
    "n_tool_calls_mean",
    "n_tool_rounds_mean",
    "wall_time_s_mean",
    # end-to-end verdicts (benchmarks/scoring.py); appended so older readers keep working
    "solved_rate",
    "solved_count",
    "solved_total",
    "abstained_on_solvable_rate",
    "abstained_on_solvable_count",
    "abstained_on_solvable_total",
    # task-level verification outcome (final_gate methods only; None for the rest)
    "verification_pass_first_rate",
    "verification_pass_retry_rate",
    "verification_abstained_rate",
    "verification_total",
    # "normal" (default) or "stress": disambiguates (model, method, case) collisions when
    # the same method/case is run under different conditions (see --condition).
    "condition",
]

CASE_SCOREBOARD_FIELDS = [
    "case_name",
    *CORE_SCOREBOARD_FIELDS,
]

# Update these values or provide --pricing-file before relying on cost numbers.
PRICE_BOOK_USD_PER_1M: dict[str, dict[str, float]] = {}


@dataclass(frozen=True)
class UsageStats:
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model: str

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}"


RULE_BASED_MODEL = ModelSpec(provider="none", model="rule_based")


@dataclass(frozen=True)
class TaskSpec:
    """Legacy single-prompt LLM-only task (baseline_pf / blueprint_pf).

    ``prompt_builder(case_name, net)`` receives the (possibly perturbed) network.
    """

    name: str
    prompt_builder: Callable[[str, Any], tuple[str, str]]
    response_parser: Callable[[str, dict[str, Any]], Any]
    context_builder: Optional[Callable[[str], dict[str, Any]]] = None
    supports_perturbation: bool = True


# ---------------------------------------------------------------------------- methods

STRATEGIES = ("structured", "few_shot", "cot", "rag")
ARCH_METHODS: dict[str, dict[str, Any]] = {
    # name: (architecture, gate, memory, final_gate)
    "react": {"architecture": "react", "gate": True, "memory": False},
    "react_nogate": {"architecture": "react", "gate": False, "memory": False},
    "plan_act": {"architecture": "plan_act", "gate": True, "memory": False},
    "plan_act_nogate": {"architecture": "plan_act", "gate": False, "memory": False},
    # PFAgent = ReAct with no in-loop observation gate, plus the task-level final-answer
    # verification V(x,c,z,y) (llm.engine.verify_final_answer). "pfagent_obsgate" keeps
    # the old (pre-V) behaviour reachable under its own name, for the already-reported
    # stress-set numbers (results_stress_gpt-4o-mini_gate3) that used it.
    "pfagent": {"architecture": "react", "gate": False, "memory": True, "final_gate": True},
    "pfagent_obsgate": {"architecture": "react", "gate": True, "memory": True, "final_gate": False},
}
METHOD_HELP = (
    "baseline_pf | blueprint_pf | llm_only:<strategy> | single_call:<strategy> | "
    + " | ".join(ARCH_METHODS)
    + " | rule_based   (strategy in "
    + "|".join(STRATEGIES)
    + ")"
)


@dataclass(frozen=True)
class MethodSpec:
    name: str
    kind: str  # "task" | "llm_only" | "engine" | "rule_based"
    strategy: Optional[str] = None
    architecture: Optional[str] = None
    gate: bool = True
    final_gate: bool = False
    memory: bool = False
    preload_case: bool = False  # the case is loaded before the method runs (single_call prompting)
    uses_llm: bool = True
    forced: bool = False  # llm_only without the escape clause: best-effort numbers required


def parse_method(name: str) -> MethodSpec:
    raw = str(name).strip()
    if raw in TASKS:
        return MethodSpec(name=raw, kind="task", uses_llm=True)
    if raw == "rule_based":
        return MethodSpec(name=raw, kind="rule_based", uses_llm=False)
    if raw in ARCH_METHODS:
        return MethodSpec(name=raw, kind="engine", **ARCH_METHODS[raw])
    head, sep, strategy = raw.partition(":")
    if sep and head in ("llm_only", "llm_only_forced", "single_call"):
        if strategy not in STRATEGIES:
            raise ValueError(f"Unknown strategy {strategy!r} in method {raw!r}; expected one of {STRATEGIES}")
        if head == "llm_only":
            return MethodSpec(name=raw, kind="llm_only", strategy=strategy)
        if head == "llm_only_forced":
            return MethodSpec(name=raw, kind="llm_only", strategy=strategy, forced=True)
        return MethodSpec(
            name=raw, kind="engine", strategy=strategy, architecture="single_call", gate=True, memory=False, preload_case=True
        )
    raise ValueError(f"Unknown method {raw!r}. Expected {METHOD_HELP}")


# ---------------------------------------------------------------------------- response helpers


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, dict):
                    text = text.get("value")
                if text is None:
                    text = part.get("content")
                if text is not None:
                    chunks.append(str(text))
            else:
                text = getattr(part, "text", None)
                if text is not None:
                    chunks.append(str(text))
        return "\n".join(c for c in chunks if c)
    return str(content or "")


def _extract_response_text(resp: Any) -> str:
    if isinstance(resp, dict):
        msg = resp.get("choices", [{}])[0].get("message", {})
        return _content_to_text(msg.get("content", ""))
    try:
        return _content_to_text(resp.choices[0].message.content)
    except Exception:
        return str(resp)


def _extract_usage(resp: Any) -> UsageStats:
    usage = getattr(resp, "usage", None)
    if usage is None and isinstance(resp, dict):
        usage = resp.get("usage")
    if usage is None:
        return UsageStats(None, None, None)

    def _read(name: str) -> Optional[int]:
        if isinstance(usage, dict):
            val = usage.get(name)
        else:
            val = getattr(usage, name, None)
        return int(val) if val is not None else None

    prompt = _read("prompt_tokens")
    completion = _read("completion_tokens")
    total = _read("total_tokens")
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    return UsageStats(prompt, completion, total)


def _safe_mean(values: list[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None]
    return float(np.mean(nums)) if nums else None


def _safe_sum(values: list[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None]
    return float(np.sum(nums)) if nums else None


def _load_pricing(path: Optional[str]) -> dict[str, dict[str, float]]:
    pricing = dict(PRICE_BOOK_USD_PER_1M)
    if not path:
        return pricing
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        pricing[key] = {
            "input": float(value["input"]),
            "output": float(value["output"]),
        }
    return pricing


def _estimate_cost_usd(
    model_key: str,
    usage: UsageStats,
    pricing: dict[str, dict[str, float]],
) -> Optional[float]:
    rates = pricing.get(model_key) or pricing.get(model_key.split(":", 1)[1])
    if not rates:
        return None
    if usage.prompt_tokens is None or usage.completion_tokens is None:
        return None
    return (
        float(usage.prompt_tokens) / 1_000_000.0 * float(rates["input"])
        + float(usage.completion_tokens) / 1_000_000.0 * float(rates["output"])
    )


def _extract_first_json_object(text: str) -> Optional[dict[str, Any]]:
    s = str(text or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    start = s.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    quote = ""
    for i in range(start, len(s)):
        ch = s[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                in_string = False
            continue
        if ch in {'"', "'"}:
            in_string = True
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(s[start : i + 1])
                    return obj if isinstance(obj, dict) else None
                except Exception:
                    return None
    return None


# ---------------------------------------------------------------------------- legacy tasks


def _baseline_parser(raw_text: str, _ctx: dict[str, Any]) -> BaselineParsed:
    from baselines.llm_only import BaselineParsed, parse_llm_baseline_json

    obj, err = parse_llm_baseline_json(raw_text)
    if err:
        raise ValueError(err)
    parsed, err = BaselineParsed.from_json(obj or {})
    if err or parsed is None:
        raise ValueError(err or "baseline_parse_failed")
    return parsed


def _blueprint_parser(raw_text: str, ctx: dict[str, Any]) -> BaselineParsed:
    from baselines.llm_only import BaselineParsed
    from solver.llm_pf import validate_llm_output

    parsed = validate_llm_output(
        raw_text=str(raw_text or ""),
        m_file_path=str(ctx["m_file_path"]),
        case_name=str(ctx["case_name"]),
        debug_mode=bool(ctx.get("debug_mode", False)),
        relax_a2=True,
    )

    return BaselineParsed(
        converged=bool(parsed.converged),
        bus_vm={int(b.bus_id): float(b.vm_pu) for b in parsed.bus_voltages},
        bus_va={int(b.bus_id): float(b.va_deg) for b in parsed.bus_voltages},
        line_p={int(l.line_id): float(l.p_from_mw) for l in parsed.line_flows},
        line_loading={int(l.line_id): float(l.loading_percent or 0.0) for l in parsed.line_flows},
        line_ends={int(l.line_id): (int(l.from_bus), int(l.to_bus)) for l in parsed.line_flows},
        total_generation_mw=float(parsed.totals.total_generation_mw),
        total_load_mw=float(parsed.totals.total_load_mw),
        total_loss_mw=float(parsed.totals.total_loss_mw),
    )


def _build_baseline_messages(case_name: str, net: Any = None) -> tuple[str, str]:
    from baselines.llm_only import build_baseline_prompt
    from baselines.prompts_baseline import BASELINE_SYSTEM_PROMPT
    from solver import case_loader

    if net is None:
        net, _ = case_loader.load(case_name)
    return BASELINE_SYSTEM_PROMPT, build_baseline_prompt(case_name, net)


def _build_blueprint_messages(case_name: str, net: Any = None) -> tuple[str, str]:
    from solver.llm_pf import build_matpower_prompt_messages
    from solver.matpower_text import read_case_m_text

    matpower_text = read_case_m_text(case_name)
    return build_matpower_prompt_messages(
        matpower_text=matpower_text,
        case_name=case_name,
        debug_mode=False,
    )


def _build_blueprint_context(case_name: str) -> dict[str, Any]:
    from solver.matpower_text import get_case_m_path

    return {
        "case_name": case_name,
        "m_file_path": str(get_case_m_path(case_name)),
        "debug_mode": False,
    }


TASKS: dict[str, TaskSpec] = {
    "baseline_pf": TaskSpec(
        name="baseline_pf",
        prompt_builder=_build_baseline_messages,
        response_parser=_baseline_parser,
    ),
    "blueprint_pf": TaskSpec(
        name="blueprint_pf",
        prompt_builder=_build_blueprint_messages,
        response_parser=_blueprint_parser,
        context_builder=_build_blueprint_context,
        # The prompt is the MATPOWER .m file text, which cannot be perturbed in place.
        supports_perturbation=False,
    ),
}


# ---------------------------------------------------------------------------- clients


def _resolve_api_key(provider: str) -> str:
    p = str(provider).strip().lower()
    if p == "openai":
        return str(OPENAI_API_KEY or os.getenv("OPENAI_API_KEY") or "").strip()
    if p == "gemini":
        return str(GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if p == "openrouter":
        # OpenRouter exposes OpenAI, Anthropic and Google models behind one OpenAI-compatible API.
        # Model ids carry the vendor prefix, e.g. openrouter:openai/gpt-4o-mini, openrouter:anthropic/claude-sonnet-4.
        return str(os.getenv("OPENROUTER_API_KEY") or "").strip()
    raise ValueError(f"Unsupported provider: {provider}")


def _resolve_base_url(provider: str) -> Optional[str]:
    p = str(provider).strip().lower()
    if p == "gemini":
        return GEMINI_BASE_URL
    if p == "openrouter":
        return os.getenv("OPENROUTER_BASE_URL") or OPENROUTER_BASE_URL
    return None


def _default_client_factory(spec: ModelSpec) -> Any:
    from llm.engine import OpenAIChatClient

    return OpenAIChatClient(api_key=_resolve_api_key(spec.provider), base_url=_resolve_base_url(spec.provider))


def _call_messages(
    client: Any,
    *,
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    timeout_s: float,
) -> tuple[str, UsageStats, float]:
    t0 = time.time()
    resp = client.create(
        model=model,
        messages=messages,
        temperature=float(temperature),
        timeout=float(timeout_s),
    )
    return _extract_response_text(resp), _extract_usage(resp), float(time.time() - t0)


def _call_model(
    client: Any,
    *,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    timeout_s: float,
) -> tuple[str, UsageStats, float]:
    return _call_messages(
        client,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=temperature,
        timeout_s=timeout_s,
    )


class _ClientPool:
    """Builds one client per model lazily (LLM-free methods never need a key)."""

    def __init__(self, factory: Optional[Callable[[ModelSpec], Any]] = None):
        self._factory = factory or _default_client_factory
        self._clients: dict[str, Any] = {}

    def get(self, spec: ModelSpec) -> Any:
        if spec.key not in self._clients:
            self._clients[spec.key] = self._factory(spec)
        return self._clients[spec.key]


def _build_clients(models: list[ModelSpec]) -> dict[str, Any]:
    return {spec.key: _default_client_factory(spec) for spec in models}


# ---------------------------------------------------------------------------- perturbation


def perturbing_dispatcher(ctx: Any, *, seed: int, k: int) -> Any:
    """Default ToolDispatcher whose ``load_case`` perturbs the loaded network.

    Every load (the harness pre-load, the ground truth, or the agent calling
    ``load_case`` itself) yields the identical seed-perturbed case, so the method
    under test and the ground truth always see the same network.
    """
    from benchmarks.requests import perturb_network
    from llm.tools import build_default_dispatcher
    from solver import case_loader

    dispatcher = build_default_dispatcher(ctx)
    original = dispatcher.handlers["load_case"]

    def load_case(args: Any) -> Any:
        out = original(args)
        if ctx.net is None or (isinstance(out, dict) and out.get("error")):
            return out
        perturb_network(ctx.net, seed=int(seed), k=int(k))
        info = case_loader._calc_network_info(ctx.net, case_loader.normalize_case_name(str(args.get("case_name"))))
        if ctx.session is not None:
            ctx.session.network_info = info
        return info.model_dump()

    dispatcher.handlers["load_case"] = load_case
    return dispatcher


def perturbed_case(case_name: str, *, seed: int, k: int) -> Any:
    """Fresh copy of ``case_name`` with ``perturb_network(seed, k)`` applied."""
    from benchmarks.requests import perturb_network
    from solver import case_loader

    net, _ = case_loader.load(case_name)
    perturb_network(net, seed=int(seed), k=int(k))
    return net


# ---------------------------------------------------------------------------- items


@dataclass
class Item:
    """One evaluation unit: a request on a seed-perturbed case with its ground truth."""

    case_name: str
    seed: int  # perturbation seed actually applied
    k: int
    text: str
    intended_calls: list[dict[str, Any]]
    request_id: Optional[str] = None
    difficulty: Optional[str] = None
    expected_outcome: str = "converged"
    notes: str = ""
    gen_seed: Optional[int] = None  # request-generator seed (request mode)
    truth: Any = None  # PowerFlowResult of the intended final state
    truth_net: Any = None
    truth_tool_errors: list[dict[str, Any]] = field(default_factory=list)
    truth_error: Optional[str] = None


def execute_intended(
    case_name: str,
    intended_calls: list[dict[str, Any]],
    *,
    seed: int,
    k: int,
    solver_config: Any,
) -> tuple[Any, Any, list[dict[str, Any]]]:
    """Run ``intended_calls`` on a fresh perturbed case; return (final PowerFlowResult, net, tool_errors)."""
    from llm.tools import ToolContext
    from models.schemas import SessionState
    from solver.power_flow import run_power_flow

    ctx = ToolContext(session=SessionState(), solver_config=solver_config)
    dispatcher = perturbing_dispatcher(ctx, seed=seed, k=k)
    errors: list[dict[str, Any]] = []
    calls = list(intended_calls)
    if not calls or calls[0].get("tool") != "load_case":
        calls = [{"tool": "load_case", "args": {"case_name": case_name}}] + calls
    for call in calls:
        tool, args = str(call["tool"]), dict(call.get("args") or {})
        out = json.loads(dispatcher.dispatch(tool, args))
        if isinstance(out, dict) and out.get("error"):
            errors.append({"tool": tool, "args": args, "error": out.get("error")})
    truth = run_power_flow(ctx.net, config=solver_config)
    return truth, ctx.net, errors


def _load_requests_file(path: str) -> list[Any]:
    from benchmarks.requests import from_jsonl

    return from_jsonl(path)


def build_items(
    case_name: str,
    *,
    seed: int,
    k: int,
    solver_config: Any,
    gen_requests: int = 0,
    requests: Optional[list[Any]] = None,
    difficulties: Optional[list[str]] = None,
) -> list[Item]:
    """Items for one (case, seed).

    * No requests: a single default power-flow item perturbed with ``seed``.
    * ``gen_requests``: ``generate_requests(case, N, seed)``; each request carries
      its own perturbation seed (``Request.seed``), as in ``compute_ground_truth``.
    * ``requests``: pre-generated requests (filtered to ``case_name``).
    """
    from solver import case_loader

    canonical = case_loader.normalize_case_name(case_name)
    items: list[Item] = []
    if requests is None and not gen_requests:
        intended = [{"tool": "load_case", "args": {"case_name": canonical}}, {"tool": "run_powerflow", "args": {}}]
        items.append(Item(case_name=canonical, seed=int(seed), k=int(k), text=DEFAULT_REQUEST_TEXT.format(case_name=canonical), intended_calls=intended))
    else:
        if requests is None:
            from benchmarks.requests import generate_requests

            requests = generate_requests(canonical, int(gen_requests), int(seed), difficulties or None)
        for req in requests:
            if case_loader.normalize_case_name(req.case_name) != canonical:
                continue
            items.append(
                Item(
                    case_name=canonical,
                    seed=int(req.seed),
                    k=int(k),
                    text=req.text,
                    intended_calls=[dict(c) for c in req.intended_calls],
                    request_id=req.id,
                    difficulty=req.difficulty,

                    expected_outcome=str(getattr(req, "expected_outcome", "converged")),
                    notes=req.notes,
                    gen_seed=int(seed),
                )
            )

    for item in items:
        try:
            item.truth, item.truth_net, item.truth_tool_errors = execute_intended(
                item.case_name, item.intended_calls, seed=item.seed, k=item.k, solver_config=solver_config
            )
            if item.truth is None or (not item.truth.converged and item.expected_outcome == "converged"):
                item.truth_error = "GroundTruthNotConverged"
        except Exception as exc:  # pragma: no cover - defensive
            item.truth_error = f"{type(exc).__name__}: {exc}"
    return items


# ---------------------------------------------------------------------------- per-item evaluation


def _truncate_trace(trace: Optional[dict[str, Any]], limit: int) -> Optional[dict[str, Any]]:
    if not trace:
        return trace
    out = copy.deepcopy(trace)
    for rnd in out.get("rounds") or []:
        for tc in rnd.get("tools") or []:
            if isinstance(tc.get("output"), str) and len(tc["output"]) > limit:
                tc["output"] = tc["output"][:limit]
    return out


def _numeric_metrics(parsed: Any, item: Item, net: Any, solver_config: Any) -> Optional[dict[str, Any]]:
    from baselines.llm_only import evaluate_against_truth_extended

    if parsed is None or item.truth is None:
        return None
    return evaluate_against_truth_extended(
        parsed,
        item.truth,
        net=net,
        v_min=solver_config.v_min,
        v_max=solver_config.v_max,
        max_loading=solver_config.max_loading,
    )


def evaluate_item(
    *,
    method: MethodSpec,
    model_spec: ModelSpec,
    client: Any,
    item: Item,
    run_idx: int,
    temperature: float,
    timeout_s: float,
    pricing: dict[str, dict[str, float]],
    solver_config: Any,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    full_trace_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Evaluate one method on one item; returns a JSON-serializable result row.

    When ``full_trace_dir`` is given, the untruncated trace, the final answer and the request are
    also written to ``<full_trace_dir>/<method>/<case>/<request_id>_run<k>.json`` for qualitative analysis.
    """
    from baselines.llm_only import baseline_parsed_from_result
    from llm.tools import ToolContext
    from models.schemas import SessionState
    from solver.power_flow import run_power_flow

    raw_text: Optional[str] = None
    usage = UsageStats(None, None, None)
    latency_s: Optional[float] = None
    metrics: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    trace: Optional[dict[str, Any]] = None
    executed: Optional[list[dict[str, Any]]] = None
    final_converged: Optional[bool] = None
    formulation: Optional[dict[str, Any]] = None
    ok = False

    session = SessionState()
    ctx = ToolContext(session=session, solver_config=solver_config)
    dispatcher = perturbing_dispatcher(ctx, seed=item.seed, k=item.k)
    preloaded_case: Optional[str] = None

    try:
        if item.truth_error:
            raise RuntimeError(item.truth_error)

        if method.kind in ("task", "llm_only"):
            net = perturbed_case(item.case_name, seed=item.seed, k=item.k)
            if method.kind == "task":
                task = TASKS[method.name]
                if item.k > 0 and not task.supports_perturbation:
                    raise ValueError(f"{task.name} reads the MATPOWER .m file and cannot be perturbed; use --k 0")
                system_prompt, user_prompt = task.prompt_builder(item.case_name, net)
                parser_ctx = task.context_builder(item.case_name) if task.context_builder else {}
                parser = task.response_parser
            else:
                from llm.prompt_variants import build_messages

                msgs = build_messages(method.strategy, "llm_only", item.text, net, item.case_name, forced=bool(getattr(method, "forced", False)))
                system_prompt, user_prompt = msgs[0]["content"], msgs[1]["content"]
                parser_ctx = {}
                parser = _baseline_parser
            raw_text, usage, latency_s = _call_model(
                client,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model_spec.model,
                temperature=temperature,
                timeout_s=timeout_s,
            )
            trace = {
                "architecture": method.name,
                "rounds": [],
                "n_llm_calls": 1,
                "n_tool_calls": 0,
                "n_tool_rounds": 0,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "wall_time_s": latency_s,
                "status": "ok",
            }
            try:
                parsed = parser(raw_text, parser_ctx)
                formulation = {"formulation_exact": None, "formulation_error_type": None, "detail": "no tool stage"}
            except Exception as exc:
                parsed = None
                formulation = {
                    "formulation_exact": None,
                    "formulation_error_type": "unparsed",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
                raise
            finally:
                if parsed is not None:
                    final_converged = bool(parsed.converged)
                    metrics = _numeric_metrics(parsed, item, net, solver_config)

        elif method.kind == "engine":
            from llm.engine import EngineConfig, LLMEngine

            if method.preload_case:
                dispatcher.dispatch("load_case", {"case_name": item.case_name})
                preloaded_case = item.case_name
            if method.architecture == "single_call":
                from llm.prompt_variants import build_messages

                msgs = build_messages(method.strategy, "single_call", item.text, ctx.net, item.case_name)
                system_prompt, user_message = msgs[0]["content"], msgs[1]["content"]
            else:
                from llm.prompts import SYSTEM_PROMPT_EN

                system_prompt, user_message = SYSTEM_PROMPT_EN, item.text
            cfg = EngineConfig(
                model=model_spec.model,
                temperature=float(temperature),
                timeout_s=float(timeout_s),
                architecture=method.architecture,
                gate=bool(method.gate),
                final_gate=bool(method.final_gate),
                memory=bool(method.memory),
                max_rounds=int(max_rounds),
                trace_output_chars=TRACE_OUTPUT_CHARS_FULL,
            )
            engine = LLMEngine(client=client, dispatcher=dispatcher, system_prompt=system_prompt, config=cfg)
            raw_text, trace = engine.run_with_trace(user_message, session)
            latency_s = trace.get("wall_time_s")
            usage = UsageStats(
                trace.get("prompt_tokens"),
                trace.get("completion_tokens"),
                (trace.get("prompt_tokens") or 0) + (trace.get("completion_tokens") or 0),
            )
            executed = None if trace.get("formulation_failure") else bm.executed_calls_from_trace(trace)
            if trace.get("status") == "llm_error":
                raise RuntimeError(raw_text)

        elif method.kind == "rule_based":
            from baselines import rule_based
            from llm.engine import gate_verdict

            t0 = time.perf_counter()
            out = rule_based.run(item.text, ctx, dispatcher)
            wall = time.perf_counter() - t0
            raw_text = out.get("answer")
            latency_s = wall
            usage = UsageStats(0, 0, 0)
            tools_rec = []
            gate_checked = gate_failed = 0
            for o in out.get("outputs") or []:
                output_str = json.dumps(o["output"], ensure_ascii=False, default=str)
                verdict = gate_verdict(output_str)
                if verdict is not None:
                    gate_checked += 1
                    gate_failed += 0 if verdict["passed"] else 1
                tools_rec.append({"name": o["tool"], "arguments": o["args"], "output": output_str, "gate": verdict})
            trace = {
                "architecture": "rule_based",
                "status": out.get("status"),
                "rounds": [{"round": 1, "tools": tools_rec}] if tools_rec else [],
                "plan": out.get("plan"),
                "warnings": out.get("warnings"),
                "formulation_failure": out.get("status") == "cannot_parse",
                "n_llm_calls": 0,
                "n_tool_calls": len(tools_rec),
                "n_tool_rounds": 1 if tools_rec else 0,
                "gate_checked": gate_checked,
                "gate_failed": gate_failed,
                "gate_enforced": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "wall_time_s": wall,
            }
            executed = None if out.get("status") == "cannot_parse" else [{"tool": o["tool"], "args": o["args"]} for o in out.get("outputs") or []]
        else:  # pragma: no cover
            raise ValueError(f"Unknown method kind: {method.kind}")

        if method.kind in ("engine", "rule_based"):
            formulation = bm.formulation_check(item.intended_calls, executed, preloaded_case=preloaded_case)
            if executed is None:
                raise RuntimeError(f"formulation_failure: {formulation.get('detail')}")
            final_result = session.last_result
            if final_result is None and ctx.net is not None and executed:
                # Mirror the ground truth: re-solve the final network state.
                final_result = run_power_flow(ctx.net, config=solver_config)
            if final_result is not None:
                final_converged = bool(final_result.converged)
                metrics = _numeric_metrics(baseline_parsed_from_result(final_result), item, ctx.net, solver_config)
            if metrics is None:
                raise RuntimeError("no_solver_result: the method produced no power-flow state to score")
        ok = metrics is not None
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        ok = False

    if formulation is None:
        formulation = {"formulation_exact": None, "formulation_error_type": None, "detail": error or ""}

    faith = bm.faithful_numbers(raw_text, bm.tool_outputs_from_trace(trace), request_text=item.text)
    truth_converged = bool(item.truth.converged) if item.truth is not None else None
    has_tools = method.kind in ("engine", "rule_based")
    # JSON-aware failure reporting and the end-to-end `solved` verdict (benchmarks/scoring.py).
    failure = bs.failure_reporting(
        raw_text,
        truth_converged=truth_converged,
        final_converged=False if item.expected_outcome != "converged" else final_converged,
        gate_failed=int((trace or {}).get("gate_failed") or 0),
        has_tools=has_tools,
    )
    solved = bs.solved_check(
        ok=ok,
        has_tools=has_tools,
        formulation_exact=formulation.get("formulation_exact"),
        truth_converged=truth_converged,
        final_converged=False if item.expected_outcome != "converged" else final_converged,
        metrics=metrics,
        answer_text=raw_text,
        truth_answer=getattr(item, "truth_answer", None) or (getattr(getattr(item, "request", None), "ground_truth", None) or {}).get("answer"),
        expected_outcome=item.expected_outcome,
        declared_failure=failure.get("safe_failure"),
    )
    stale = bm.stale_state_check(trace, raw_text, request_text=item.text)
    cost = bm.cost_from_trace(trace)
    cost_usd = _estimate_cost_usd(model_spec.key, usage, pricing) if method.uses_llm else 0.0

    if full_trace_dir is not None:
        try:
            _loc = locals()
            _tr = _loc.get("trace")
            _payload = {
                "method": method.name,
                "model": model_spec.key,
                "case_name": item.case_name,
                "request_id": item.request_id,
                "seed": item.seed,
                "run": run_idx,
                "difficulty": getattr(item, "difficulty", None),
                "request_text": item.text,
                "intended_calls": getattr(item, "intended_calls", None),
                "executed_calls": _loc.get("executed"),
                "answer": _loc.get("raw_text"),
                "trace": _tr,
            }
            _dir = Path(full_trace_dir) / re.sub(r"[^A-Za-z0-9_.-]+", "_", method.name) / str(item.case_name)
            _dir.mkdir(parents=True, exist_ok=True)
            _write_json(_dir / f"{item.request_id or 'default'}_run{run_idx}.json", _payload)
        except Exception as _e:  # never let logging break a run
            print(f"[trace-dump] skipped: {_e}")

    return {
        "model": model_spec.key,
        "provider": model_spec.provider,
        "task": method.name,
        "method": method.name,
        "case_name": item.case_name,
        "run": int(run_idx),
        "k": int(item.k),
        "seed": int(item.seed),
        "gen_seed": item.gen_seed,
        "request_id": item.request_id,
        "difficulty": item.difficulty,
        "request_text": item.text,
        "ok": bool(ok),
        "error": error,
        "latency_s": latency_s,
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        },
        "cost_usd": cost_usd,
        "metrics": metrics,
        "raw_response": raw_text,
        "intended_calls": item.intended_calls,
        "executed_calls": executed,
        "formulation_exact": formulation.get("formulation_exact"),
        "formulation_error_type": formulation.get("formulation_error_type"),
        "formulation_detail": formulation.get("detail"),
        "faithful_numbers": faith["faithful_numbers"],
        "n_numbers": faith["n_numbers"],
        "n_untraceable_numbers": faith["n_untraceable_numbers"],
        "untraceable_numbers": faith["untraceable"],
        "final_converged": final_converged,
        "expected_outcome": item.expected_outcome,
        "truth_converged": truth_converged,
        "truth_tool_errors": item.truth_tool_errors,
        "solved": solved["solved"],
        "solved_reason": solved["solved_reason"],
        "is_failure": failure["is_failure"],
        "safe_failure": failure["safe_failure"],
        "claimed_success_on_failure": failure["claimed_success_on_failure"],
        "abstained": failure["abstained"],
        "abstained_on_solvable": failure["abstained_on_solvable"],
        "failure_detection_path": failure["detection_path"],
        "has_mutation": stale["has_mutation"],
        "stale_state": stale["stale_state"],
        "stale_state_no_rerun": stale["stale_state_no_rerun"],
        "stale_state_quoted_old": stale["stale_state_quoted_old"],
        "stale_state_detail": stale["detail"],
        "stale_state_trace": {
            k: stale[k]
            for k in ("last_mutation_index", "last_mutation_tool", "last_mutation_args", "prior_result_indices", "resolve_indices_after", "old_only")
        },
        "verification_outcome": (trace or {}).get("verification_outcome"),
        "verification_attempts": (trace or {}).get("verification_attempts"),
        **cost,
        "trace": _truncate_trace(trace, TRACE_OUTPUT_CHARS_REPORT),
    }


# ---------------------------------------------------------------------------- aggregation


def _aggregate_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [r for r in rows if r.get("ok")]
    form = bm.rate([r.get("formulation_exact") for r in rows])
    safe = bm.rate([r.get("safe_failure") for r in rows])
    claimed = bm.rate([r.get("claimed_success_on_failure") for r in rows])
    stale = bm.rate([r.get("stale_state") for r in rows])
    stale_no_rerun = bm.rate([r.get("stale_state_no_rerun") for r in rows])
    stale_quoted_old = bm.rate([r.get("stale_state_quoted_old") for r in rows])
    solved = bm.rate([r.get("solved") for r in rows])
    abstained = bm.rate([r.get("abstained_on_solvable") for r in rows])
    verif_outcomes = [r.get("verification_outcome") for r in rows if r.get("verification_outcome") is not None]
    verif_total = len(verif_outcomes)

    def _verif_rate(name: str) -> Optional[float]:
        return (sum(1 for v in verif_outcomes if v == name) / verif_total) if verif_total else None
    scoreboard = {
        # `success_rate` = run completed and parsed (kept for backward compatibility);
        # `solved_rate` = answered correctly end to end (benchmarks/scoring.py).
        "success_rate": float(len(ok_rows) / len(rows)) if rows else 0.0,
        "solved_rate": solved["rate"],
        "solved_count": solved["count"],
        "solved_total": solved["total"],
        "voltage_mae_mean": _safe_mean([(r.get("metrics") or {}).get("voltage_mae") for r in ok_rows]),
        "flow_mae_mean": _safe_mean([(r.get("metrics") or {}).get("flow_mae") for r in ok_rows]),
        "loading_rmse_mean": _safe_mean([(r.get("metrics") or {}).get("loading_rmse") for r in ok_rows]),
        "voltage_f1_mean": _safe_mean([(r.get("metrics") or {}).get("voltage_f1") for r in ok_rows]),
        "thermal_f1_mean": _safe_mean([(r.get("metrics") or {}).get("thermal_f1") for r in ok_rows]),
        "convergence_match_rate": _safe_mean([
            1.0 if (r.get("metrics") or {}).get("convergence_match") else 0.0 for r in ok_rows
        ]),
        "convergence_match_count": sum(1 for r in ok_rows if (r.get("metrics") or {}).get("convergence_match")),
        "convergence_match_total": len(ok_rows),
        "prompt_tokens_mean": _safe_mean([(r.get("usage") or {}).get("prompt_tokens") for r in rows]),
        "completion_tokens_mean": _safe_mean([(r.get("usage") or {}).get("completion_tokens") for r in rows]),
        "total_tokens_mean": _safe_mean([(r.get("usage") or {}).get("total_tokens") for r in rows]),
        "cost_usd_mean": _safe_mean([r.get("cost_usd") for r in rows]),
        "cost_usd_total": _safe_sum([r.get("cost_usd") for r in rows]),
        # R1 additions
        "n_items": len(rows),
        "formulation_exact_rate": form["rate"],
        "formulation_exact_count": form["count"],
        "formulation_exact_total": form["total"],
        "formulation_error_counts": bm.error_type_counts([r.get("formulation_error_type") for r in rows]),
        "faithful_numbers_mean": _safe_mean([r.get("faithful_numbers") for r in rows]),
        "n_untraceable_numbers_mean": _safe_mean([r.get("n_untraceable_numbers") for r in rows if r.get("n_numbers")]),
        "safe_failure_rate": safe["rate"],
        "safe_failure_count": safe["count"],
        "safe_failure_total": safe["total"],
        "claimed_success_on_failure_rate": claimed["rate"],
        "claimed_success_on_failure_count": claimed["count"],
        "claimed_success_on_failure_total": claimed["total"],
        "abstained_on_solvable_rate": abstained["rate"],
        "abstained_on_solvable_count": abstained["count"],
        "abstained_on_solvable_total": abstained["total"],
        "stale_state_rate": stale["rate"],
        "stale_state_count": stale["count"],
        "stale_state_total": stale["total"],
        "stale_state_no_rerun_rate": stale_no_rerun["rate"],
        "stale_state_no_rerun_count": stale_no_rerun["count"],
        "stale_state_no_rerun_total": stale_no_rerun["total"],
        "stale_state_quoted_old_rate": stale_quoted_old["rate"],
        "stale_state_quoted_old_count": stale_quoted_old["count"],
        "stale_state_quoted_old_total": stale_quoted_old["total"],
        "converged_rate": bm.rate([r.get("final_converged") for r in rows])["rate"],
        "kcl_mean_mismatch_mw_mean": _safe_mean([(r.get("metrics") or {}).get("kcl_mean_mismatch_mw") for r in ok_rows]),
        "power_balance_error_mean": _safe_mean([(r.get("metrics") or {}).get("power_balance_error") for r in ok_rows]),
        "n_llm_calls_mean": _safe_mean([r.get("n_llm_calls") for r in rows]),
        "n_tool_calls_mean": _safe_mean([r.get("n_tool_calls") for r in rows]),
        "n_tool_rounds_mean": _safe_mean([r.get("n_tool_rounds") for r in rows]),
        "wall_time_s_mean": _safe_mean([r.get("wall_time_s", r.get("latency_s")) for r in rows]),
        "verification_pass_first_rate": _verif_rate("pass_first"),
        "verification_pass_retry_rate": _verif_rate("pass_retry"),
        "verification_abstained_rate": _verif_rate("abstained"),
        "verification_total": verif_total,
    }
    return scoreboard


# ---------------------------------------------------------------------------- writers


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def _rate_cell(row: dict[str, Any], prefix: str) -> str:
    rate = row.get(f"{prefix}_rate")
    if rate is None:
        return "n/a"
    return f"{rate:.2f} ({row.get(f'{prefix}_count')}/{row.get(f'{prefix}_total')})"


_MD_COLUMNS = [
    ("success_rate", lambda r: _fmt(r.get("success_rate"))),
    ("solved", lambda r: _rate_cell(r, "solved")),
    ("voltage_mae", lambda r: _fmt(r.get("voltage_mae_mean"))),
    ("flow_mae", lambda r: _fmt(r.get("flow_mae_mean"))),
    ("loading_rmse", lambda r: _fmt(r.get("loading_rmse_mean"))),
    ("voltage_f1", lambda r: _fmt(r.get("voltage_f1_mean"))),
    ("thermal_f1", lambda r: _fmt(r.get("thermal_f1_mean"))),
    ("conv_match", lambda r: _fmt(r.get("convergence_match_rate"))),
    ("prompt_tokens", lambda r: _fmt(r.get("prompt_tokens_mean"))),
    ("completion_tokens", lambda r: _fmt(r.get("completion_tokens_mean"))),
    ("total_tokens", lambda r: _fmt(r.get("total_tokens_mean"))),
    ("cost_usd_mean", lambda r: _fmt(r.get("cost_usd_mean"))),
    ("cost_usd_total", lambda r: _fmt(r.get("cost_usd_total"))),
    ("formulation_exact", lambda r: _rate_cell(r, "formulation_exact")),
    ("faithful_numbers", lambda r: _fmt(r.get("faithful_numbers_mean"))),
    ("safe_failure", lambda r: _rate_cell(r, "safe_failure")),
    ("claimed_success_on_failure", lambda r: _rate_cell(r, "claimed_success_on_failure")),
    ("abstained_on_solvable", lambda r: _rate_cell(r, "abstained_on_solvable")),
    ("stale_state", lambda r: _rate_cell(r, "stale_state")),
    ("stale_no_rerun", lambda r: _rate_cell(r, "stale_state_no_rerun")),
    ("stale_quoted_old", lambda r: _rate_cell(r, "stale_state_quoted_old")),
    ("llm_calls", lambda r: _fmt(r.get("n_llm_calls_mean"))),
    ("tool_calls", lambda r: _fmt(r.get("n_tool_calls_mean"))),
    ("wall_s", lambda r: _fmt(r.get("wall_time_s_mean"))),
]


def _markdown_table(scoreboard: list[dict[str, Any]], key_cols: list[str]) -> str:
    header = "| " + " | ".join(key_cols + [c for c, _ in _MD_COLUMNS]) + " |\n"
    sep = "|" + "|".join(["---"] * len(key_cols) + ["---:"] * len(_MD_COLUMNS)) + "|\n"
    lines = [header, sep]
    for row in scoreboard:
        cells = [str(row.get(c)) for c in key_cols] + [fn(row) for _, fn in _MD_COLUMNS]
        lines.append("| " + " | ".join(cells) + " |\n")
    return "".join(lines)


def _write_markdown(path: Path, scoreboard: list[dict[str, Any]], config: Optional[dict[str, Any]] = None) -> None:
    lines = ["# LLM Power-Flow Benchmark\n\n"]
    if config:
        lines.append(
            f"k={config.get('k')}, seeds={config.get('seeds')}, cases={config.get('cases')}, "
            f"max_rounds={config.get('max_rounds')}, requests={config.get('requests')}\n\n"
        )
    lines.append(_markdown_table(scoreboard, ["model", "task"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def _write_case_markdown(path: Path, scoreboard: list[dict[str, Any]]) -> None:
    lines = ["# LLM Power-Flow Benchmark (Per Case)\n\n", _markdown_table(scoreboard, ["model", "task", "case_name"])]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------- runner


def run_benchmark(
    *,
    models: list[ModelSpec],
    tasks: Optional[list[str]] = None,
    cases: list[str],
    runs: int,
    temperature: float,
    timeout_s: float,
    pricing: dict[str, dict[str, float]],
    solver_config: Any,
    methods: Optional[list[str]] = None,
    k: int = 0,
    seeds: Optional[list[int]] = None,
    requests_path: Optional[str] = None,
    gen_requests: int = 0,
    difficulties: Optional[list[str]] = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    client_factory: Optional[Callable[[ModelSpec], Any]] = None,
    verbose: bool = True,
    full_trace_dir: Optional[Path] = None,
    condition: str = "normal",
) -> dict[str, Any]:
    """Run every (model, method, case, seed, item, run) and aggregate.

    ``tasks`` is the legacy name for ``methods``; both accept method names.
    Defaults (``k=0``, ``seeds=[0]``, no requests) reproduce the pre-R1 run.
    ``condition`` ("normal" by default, "stress" for the stress-difficulty sets) is
    stamped on every scoreboard row so fill_table.py can key on (model, method, case,
    condition) instead of silently merging a stress run into a normal one that shares
    the same (model, method, case) — see fill_table.load_case_rows.
    """
    method_names = list(methods or tasks or [])
    if not method_names:
        raise ValueError("No methods given")
    method_specs = [parse_method(m) for m in method_names]
    seeds = list(seeds) if seeds else [0]
    pool = _ClientPool(client_factory)

    file_requests: Optional[list[Any]] = _load_requests_file(requests_path) if requests_path else None
    if file_requests is not None and len(seeds) > 1:
        print("--requests carries its own per-request seeds; ignoring additional --seeds", file=sys.stderr)
        seeds = seeds[:1]

    raw_rows: list[dict[str, Any]] = []
    for case_name in cases:
        for seed in seeds:
            items = build_items(
                case_name,
                seed=int(seed),
                k=int(k),
                solver_config=solver_config,
                gen_requests=int(gen_requests),
                requests=file_requests,
                difficulties=difficulties,
            )
            if k == 0 and any(it.truth_error for it in items) and not (gen_requests or file_requests):
                raise RuntimeError(f"Ground-truth solver did not converge for {case_name}")
            for method in method_specs:
                model_list = list(models) if method.uses_llm else [RULE_BASED_MODEL]
                for model_spec in model_list:
                    client = pool.get(model_spec) if method.uses_llm else None
                    for item in items:
                        for run_idx in range(int(runs)):
                            if verbose:
                                tag = item.request_id or "default"
                                print(f"{method.name} {model_spec.key} {case_name} seed={item.seed} k={k} {tag} run ID: {run_idx}")
                            raw_rows.append(
                                evaluate_item(
                                    method=method,
                                    model_spec=model_spec,
                                    client=client,
                                    item=item,
                                    run_idx=run_idx,
                                    temperature=temperature,
                                    timeout_s=timeout_s,
                                    pricing=pricing,
                                    solver_config=solver_config,
                                    max_rounds=max_rounds,
                                    full_trace_dir=full_trace_dir,
                                )
                            )

    scoreboard_rows: list[dict[str, Any]] = []
    scoreboard_case_rows: list[dict[str, Any]] = []
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_case_group: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in raw_rows:
        by_group.setdefault((row["model"], row["task"]), []).append(row)
        by_case_group.setdefault((row["model"], row["task"], row["case_name"]), []).append(row)

    for (model_key, task_name), rows in sorted(by_group.items()):
        agg = _aggregate_group(rows)
        scoreboard_rows.append({"model": model_key, "task": task_name, "method": task_name, "condition": condition, **agg})

    for (model_key, task_name, case_name), rows in sorted(by_case_group.items()):
        agg = _aggregate_group(rows)
        scoreboard_case_rows.append(
            {"model": model_key, "task": task_name, "method": task_name, "case_name": case_name, "condition": condition, **agg}
        )

    return {
        "config": {
            "models": [m.key for m in models],
            "tasks": method_names,
            "methods": method_names,
            "cases": cases,
            "condition": condition,
            "runs": runs,
            "k": int(k),
            "seeds": [int(s) for s in seeds],
            "max_rounds": int(max_rounds),
            "requests": (
                {"source": requests_path}
                if requests_path
                else {"source": "generated", "n_per_case_seed": int(gen_requests), "difficulties": difficulties}
                if gen_requests
                else None
            ),
            "temperature": temperature,
            "timeout_s": timeout_s,
            "solver_config": {
                "v_min": solver_config.v_min,
                "v_max": solver_config.v_max,
                "max_loading": solver_config.max_loading,
            },
        },
        "core_scoreboard_fields": CORE_SCOREBOARD_FIELDS,
        "extended_scoreboard_fields": EXTENDED_SCOREBOARD_FIELDS,
        "metric_definitions": bm.__doc__,
        "scoreboard": scoreboard_rows,
        "scoreboard_per_case": scoreboard_case_rows,
        "runs": raw_rows,
    }


def _flatten_scoreboard(scoreboard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for row in scoreboard:
        flat.append({k: row.get(k) for k in ["model", "task", *CORE_SCOREBOARD_FIELDS, *EXTENDED_SCOREBOARD_FIELDS]})
    return flat


def _flatten_case_scoreboard(scoreboard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for row in scoreboard:
        flat.append({k: row.get(k) for k in ["model", "task", *CASE_SCOREBOARD_FIELDS, *EXTENDED_SCOREBOARD_FIELDS]})
    return flat


def _parse_model_specs(values: list[str]) -> list[ModelSpec]:
    if not values:
        values = [f"openai:{OPENAI_MODEL}", f"gemini:{GEMINI_MODEL}"]
    specs: list[ModelSpec] = []
    for raw in values:
        provider, sep, model = raw.partition(":")
        if not sep or not model:
            raise ValueError(f"Invalid model spec: {raw}. Expected provider:model")
        specs.append(ModelSpec(provider=provider.strip().lower(), model=model.strip()))
    return specs


def _parse_seed_list(raw: Optional[str]) -> Optional[list[int]]:
    if not raw:
        return None
    return [int(s) for s in str(raw).replace(";", ",").split(",") if s.strip()]


def write_report(out_dir: Path, report: dict[str, Any]) -> None:
    _write_json(out_dir / "report.json", report)
    _write_json(out_dir / "scoreboard.json", report["scoreboard"])
    _write_csv(out_dir / "scoreboard.csv", _flatten_scoreboard(report["scoreboard"]))
    _write_markdown(out_dir / "scoreboard.md", report["scoreboard"], report.get("config"))
    _write_json(out_dir / "scoreboard_per_case.json", report["scoreboard_per_case"])
    _write_csv(out_dir / "scoreboard_per_case.csv", _flatten_case_scoreboard(report["scoreboard_per_case"]))
    _write_case_markdown(out_dir / "scoreboard_per_case.md", report["scoreboard_per_case"])


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark multiple LLMs / agent architectures on power-flow tasks.")
    parser.add_argument("--model", dest="models", action="append", default=[], help="provider:model, repeatable")
    parser.add_argument("--task", dest="tasks", action="append", choices=sorted(TASKS.keys()), default=[], help="legacy; repeatable")
    parser.add_argument("--method", dest="methods", action="append", default=[], help=f"repeatable; one of {METHOD_HELP}")
    parser.add_argument("--case", dest="cases", action="append", default=[], help="repeatable")
    parser.add_argument("--runs", dest="runs", type=int, default=1)
    parser.add_argument("--k", dest="k", type=int, default=DEFAULT_K, help="perturbation strength (+/-10%% per unit; 0 = base case)")
    parser.add_argument("--seeds", dest="seeds", type=int, default=1, help="number of perturbation seeds (0..N-1)")
    parser.add_argument("--seed-list", dest="seed_list", default=None, help="explicit comma-separated seeds (overrides --seeds)")
    parser.add_argument("--requests", dest="requests_path", default=None, help="requests .jsonl from benchmarks/requests.py")
    parser.add_argument("--gen-requests", dest="gen_requests", type=int, default=0, help="generate N requests per case and seed")
    parser.add_argument("--difficulty", dest="difficulties", action="append", default=[], help="restrict generated requests")
    parser.add_argument("--max-rounds", dest="max_rounds", type=int, default=DEFAULT_MAX_ROUNDS, help="tool-round budget for all agents")
    parser.add_argument("--temperature", dest="temperature", type=float, default=0.0)
    parser.add_argument("--timeout-s", dest="timeout_s", type=float, default=90.0)
    parser.add_argument("--pricing-file", dest="pricing_file", default=None)
    parser.add_argument("--out-dir", dest="out_dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--trace-dir", dest="trace_dir", default=None, help="directory for untruncated per-item traces (default: <out-dir>/traces)")
    parser.add_argument("--no-traces", dest="no_traces", action="store_true", help="do not write per-item trace files")
    parser.add_argument("--quiet", dest="quiet", action="store_true")
    parser.add_argument(
        "--condition",
        dest="condition",
        default=None,
        help="tag disambiguating (model, method, case) in fill_table.py when the same method/case is "
        "run more than once under different conditions (default: 'stress' if --difficulty stress is "
        "the only requested difficulty, else 'normal')",
    )

    args = parser.parse_args(argv)

    models = _parse_model_specs(args.models)
    methods = list(args.tasks) + list(args.methods)
    if not methods:
        methods = ["baseline_pf", "blueprint_pf"]
        if int(args.k) > 0:
            print("blueprint_pf cannot be perturbed (reads the .m file); dropping it from the default methods for k>0", file=sys.stderr)
            methods = ["baseline_pf"]
    for m in methods:
        parse_method(m)  # validate early
        if m in TASKS and not TASKS[m].supports_perturbation and int(args.k) > 0:
            raise SystemExit(f"{m} reads the MATPOWER .m file and cannot be perturbed; run it with --k 0")
    if args.requests_path and args.gen_requests:
        raise SystemExit("Use either --requests or --gen-requests, not both")

    cases = args.cases
    if not cases and args.requests_path:
        from solver import case_loader

        seen: list[str] = []
        for r in _load_requests_file(args.requests_path):
            c = case_loader.normalize_case_name(r.case_name)
            if c not in seen:
                seen.append(c)
        cases = seen
    cases = cases or ["case14", "case30", "case57"]
    seeds = _parse_seed_list(args.seed_list) or list(range(int(args.seeds)))
    pricing = _load_pricing(args.pricing_file)
    from solver.power_flow import SolverConfig

    solver_config = SolverConfig()

    condition = args.condition
    if condition is None:
        condition = "stress" if list(args.difficulties or []) == ["stress"] else "normal"

    report = run_benchmark(
        models=models,
        methods=methods,
        cases=cases,
        runs=int(args.runs),
        temperature=float(args.temperature),
        timeout_s=float(args.timeout_s),
        pricing=pricing,
        solver_config=solver_config,
        k=int(args.k),
        seeds=seeds,
        requests_path=args.requests_path,
        gen_requests=int(args.gen_requests),
        difficulties=args.difficulties or None,
        max_rounds=int(args.max_rounds),
        verbose=not args.quiet,
        full_trace_dir=None if args.no_traces else Path(args.trace_dir or (Path(args.out_dir) / "traces")),
        condition=condition,
    )

    write_report(Path(args.out_dir), report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
