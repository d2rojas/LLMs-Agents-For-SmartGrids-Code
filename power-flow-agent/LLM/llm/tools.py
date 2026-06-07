"""LLM callable tools and dispatcher bindings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping, Optional

import plotly.io as pio

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    GEMINI_TIMEOUT_S,
    LLM_ONLY_DEBUG_MODE,
    MATPOWER_CASE_DATE,
    MATPOWER_DATA_ROOT,
)
from models.schemas import (
    BusVoltage,
    LineFlow,
    Modification,
    PowerFlowResult,
    SessionState,
    ViolationType,
)
from solver import case_loader
from solver.contingency import get_most_loaded_branch as _get_most_loaded_branch
from solver.contingency import run_n1_contingency as _run_n1_contingency
from solver.llm_pf import build_matpower_prompt_preview as _build_matpower_prompt_preview
from solver.llm_pf import get_last_raw_response as _get_last_raw_response
from solver.llm_pf import solve_from_matpower_text as _solve_from_matpower_text
from solver.matpower_text import FETCH_CMD as _FETCH_CMD
from solver.matpower_text import get_case_m_path as _get_case_m_path
from solver.matpower_text import read_case_m_text as _read_case_m_text
from solver.net_ops import disconnect_line as _disconnect_line_no_solve
from solver.net_ops import modify_load as _modify_load_no_solve
from solver.net_ops import reconnect_line as _reconnect_line_no_solve
from solver.power_flow import SolverConfig
from solver.power_flow import disconnect_line as _disconnect_line
from solver.power_flow import get_network_status as _get_network_status
from solver.power_flow import modify_bus_load as _modify_bus_load
from solver.power_flow import reconnect_line as _reconnect_line
from solver.power_flow import run_power_flow as _run_power_flow
from solver.remedial import apply_remedial_action_inplace as _apply_remedial_action_inplace
from solver.remedial import recommend_remedial_actions as _recommend_remedial_actions
from solver.validators import validate_result
from viz import make_comparison
from viz import make_flow_diagram
from viz import make_n1_ranking
from viz import make_remedial_ranking
from viz import make_violation_overview
from viz import make_voltage_heatmap
from viz.network_plot import build_graph as _build_graph
from viz.network_plot import compute_layout as _compute_layout

TOOLS: list[dict[str, Any]] = [
    {
        "name": "load_case",
        "description": "Load IEEE test case.",
        "parameters": {
            "type": "object",
            "properties": {"case_name": {"type": "string", "enum": ["case14", "case30", "case57", "case118", "case300"]}},
            "required": ["case_name"],
        },
    },
    {"name": "run_powerflow", "description": "Run power flow on current case.", "parameters": {"type": "object", "properties": {}}},
    {
        "name": "modify_load",
        "description": "Modify bus load and recompute.",
        "parameters": {
            "type": "object",
            "properties": {
                "bus_id": {"type": "integer"},
                "p_mw": {"type": "number"},
                "q_mvar": {"type": "number"},
            },
            "required": ["bus_id", "p_mw"],
        },
    },
    {
        "name": "disconnect_line",
        "description": "Disconnect line/branch between two buses and recompute.",
        "parameters": {
            "type": "object",
            "properties": {"from_bus": {"type": "integer"}, "to_bus": {"type": "integer"}},
            "required": ["from_bus", "to_bus"],
        },
    },
    {
        "name": "reconnect_line",
        "description": "Reconnect line/branch between two buses and recompute.",
        "parameters": {
            "type": "object",
            "properties": {"from_bus": {"type": "integer"}, "to_bus": {"type": "integer"}},
            "required": ["from_bus", "to_bus"],
        },
    },
    {"name": "get_most_loaded_branch", "description": "Get most loaded branch.", "parameters": {"type": "object", "properties": {}}},
    {
        "name": "run_n1_contingency",
        "description": "Run N-1 contingency analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "top_k": {"type": "integer", "default": 5},
                "criteria": {"type": "string", "enum": ["max_violations", "max_overload", "min_voltage"], "default": "max_violations"},
                "max_candidates": {"type": "integer", "default": 0},
            },
        },
    },
    {
        "name": "recommend_remedial_actions",
        "description": "Recommend remedial actions.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_actions": {"type": "integer", "default": 5},
                "allow_load_shed": {"type": "boolean", "default": True},
                "allow_voltage_control": {"type": "boolean", "default": True},
                "include_best_comparison": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "apply_remedial_action",
        "description": "Apply one remedial action by index.",
        "parameters": {
            "type": "object",
            "properties": {"action_index": {"type": "integer"}, "confirmed": {"type": "boolean", "default": False}},
            "required": ["action_index"],
        },
    },
    {"name": "get_status", "description": "Get current network status.", "parameters": {"type": "object", "properties": {}}},
    {
        "name": "generate_plot",
        "description": "Generate one plot.",
        "parameters": {
            "type": "object",
            "properties": {
                "plot_type": {
                    "type": "string",
                    "enum": ["voltage_heatmap", "flow_diagram", "violation_overview", "comparison"],
                }
            },
            "required": ["plot_type"],
        },
    },
]


def get_openai_tools() -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}} for t in TOOLS]


Handler = Callable[[Mapping[str, Any]], Any]


@dataclass
class ToolDispatcher:
    handlers: MutableMapping[str, Handler]

    def dispatch(self, tool_name: str, arguments: Mapping[str, Any]) -> str:
        if tool_name not in self.handlers:
            return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
        try:
            out = self.handlers[tool_name](arguments)
            if isinstance(out, str):
                return out
            return json.dumps(out, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": f"Tool failed: {tool_name}", "exception": type(e).__name__, "message": str(e)}, ensure_ascii=False)


@dataclass
class ToolContext:
    net: Any = None
    session: Optional[SessionState] = None
    solver_config: SolverConfig = SolverConfig()

    prev_result: Any = None
    last_plot_json: Optional[str] = None
    last_n1_report: Any = None
    last_plot_type: Optional[str] = None
    cached_positions: Optional[dict[int, tuple[float, float]]] = None

    theme: str = "light"
    solver_backend: str = "pandapower"
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: Optional[str] = None
    llm_temperature: float = 0.0
    llm_timeout_s: float = 90.0
    llm_only_debug_mode: bool = False
    matpower_data_root: str = MATPOWER_DATA_ROOT
    matpower_case_date: str = MATPOWER_CASE_DATE
    ui_lang: str = "en"


def build_default_dispatcher(ctx: ToolContext) -> ToolDispatcher:
    if ctx.session is None:
        ctx.session = SessionState()

    def _is_llm_only() -> bool:
        return str(ctx.solver_backend).strip().lower() == "llm_only"

    def _lang() -> str:
        return "zh" if str(ctx.ui_lang).lower().startswith("zh") else "en"

    def _llm_disabled() -> dict[str, Any]:
        return {
            "error": "This feature is disabled in LLM-only mode due to high token cost and instability. Please switch to PandaPower backend."
        }

    def _resolve_case_name_for_matpower() -> str:
        if ctx.session is not None and ctx.session.active_case:
            return str(ctx.session.active_case)
        name = getattr(ctx.net, "_case_name", None) or getattr(ctx.net, "name", None)
        if isinstance(name, str) and name.strip():
            return name.strip()
        return "case14"

    def _to_powerflow_result_schema_mapped(
        *,
        parsed: Any,
        case_name: str,
        matpower_prompt: str,
    ) -> PowerFlowResult:
        vv_type_map = {
            "overvoltage": ViolationType.OVERVOLTAGE,
            "undervoltage": ViolationType.UNDERVOLTAGE,
        }
        bus_voltages = [
            BusVoltage(
                bus_id=int(b.bus_id),
                vm_pu=float(b.vm_pu),
                va_deg=float(b.va_deg),
                is_violation=False,
                violation_type=None,
            )
            for b in parsed.bus_voltages
        ]

        line_flows = [
            LineFlow(
                line_id=int(l.line_id),
                from_bus=int(l.from_bus),
                to_bus=int(l.to_bus),
                p_from_mw=float(l.p_from_mw),
                q_from_mvar=float(l.q_from_mvar),
                loading_percent=float(l.loading_percent) if l.loading_percent is not None else 0.0,
                is_violation=False,
            )
            for l in parsed.line_flows
        ]

        voltage_violations = [
            BusVoltage(
                bus_id=int(v.bus_id),
                vm_pu=float(v.vm_pu),
                va_deg=0.0,
                is_violation=True,
                violation_type=vv_type_map.get(str(v.type)),
            )
            for v in parsed.voltage_violations
        ]

        thermal_violations = [
            LineFlow(
                line_id=int(t.line_id),
                from_bus=int(t.from_bus),
                to_bus=int(t.to_bus),
                p_from_mw=0.0,
                q_from_mvar=0.0,
                loading_percent=float(t.loading_percent),
                is_violation=True,
            )
            for t in parsed.thermal_violations
        ]

        result = PowerFlowResult(
            case_name=case_name,
            converged=bool(parsed.converged),
            bus_voltages=bus_voltages,
            line_flows=line_flows,
            total_generation_mw=float(parsed.totals.total_generation_mw),
            total_load_mw=float(parsed.totals.total_load_mw),
            total_loss_mw=float(parsed.totals.total_loss_mw),
            voltage_violations=voltage_violations,
            thermal_violations=thermal_violations,
            summary_text=str(parsed.summary_text or ""),
            solver_backend="llm_only",
            llm_prompt=matpower_prompt,
            llm_response=(_get_last_raw_response() or parsed.model_dump_json(indent=2, exclude_none=False)),
        )
        return validate_result(
            ctx.net,
            result,
            v_min=ctx.solver_config.v_min,
            v_max=ctx.solver_config.v_max,
            max_loading=ctx.solver_config.max_loading,
        )

    def _run_llm_only_pf() -> Any:
        case_name = _resolve_case_name_for_matpower()
        data_root = str(ctx.matpower_data_root or MATPOWER_DATA_ROOT)
        case_date = str(ctx.matpower_case_date or MATPOWER_CASE_DATE)

        try:
            m_path = _get_case_m_path(case_name, date=case_date, root=data_root)
            matpower_text = _read_case_m_text(case_name, date=case_date, root=data_root)
        except Exception as e:
            msg = str(e)
            out = {"error": msg}
            if _FETCH_CMD in msg:
                out["fetch_command"] = _FETCH_CMD
            return out

        provider = str(ctx.llm_provider or "gemini")
        model = str(ctx.llm_model or GEMINI_MODEL)
        api_key = str(ctx.llm_api_key or GEMINI_API_KEY or "")
        temperature = float(ctx.llm_temperature if ctx.llm_temperature is not None else GEMINI_TEMPERATURE)
        timeout_s = float(ctx.llm_timeout_s if ctx.llm_timeout_s is not None else GEMINI_TIMEOUT_S)
        debug_mode = bool(ctx.llm_only_debug_mode if ctx.llm_only_debug_mode is not None else LLM_ONLY_DEBUG_MODE)
        prompt_preview = _build_matpower_prompt_preview(
            matpower_text=matpower_text,
            case_name=case_name,
            debug_mode=debug_mode,
        )

        try:
            parsed = _solve_from_matpower_text(
                matpower_text=matpower_text,
                m_file_path=str(m_path),
                case_name=case_name,
                debug_mode=debug_mode,
                llm_provider=provider,
                llm_model=model,
                api_key=api_key,
                temperature=temperature,
                timeout_s=timeout_s,
            )
        except Exception as e:
            return {"error": str(e)}
        return _to_powerflow_result_schema_mapped(
            parsed=parsed,
            case_name=case_name,
            matpower_prompt=prompt_preview,
        )

    def _run_pf_with_backend() -> Any:
        if _is_llm_only():
            return _run_llm_only_pf()
        return _run_power_flow(ctx.net, config=ctx.solver_config)

    def load_case(args: Mapping[str, Any]) -> Any:
        net, info = case_loader.load(str(args.get("case_name")))
        ctx.net = net
        ctx.session.active_case = info.case_name
        ctx.session.network_info = info
        ctx.prev_result = None
        ctx.session.last_result = None
        ctx.session.modification_log = []
        ctx.cached_positions = None
        return info.model_dump()

    def run_powerflow(_: Mapping[str, Any]) -> Any:
        if ctx.net is None:
            return {"error": "Please load a test case first."}
        ctx.prev_result = ctx.session.last_result
        res = _run_pf_with_backend()
        if isinstance(res, dict) and res.get("error"):
            return res
        ctx.session.last_result = res
        return res.model_dump()

    def modify_load(args: Mapping[str, Any]) -> Any:
        if ctx.net is None:
            return {"error": "Please load a test case first."}
        bus_id = int(args.get("bus_id"))
        p_mw = float(args.get("p_mw"))
        q_raw = args.get("q_mvar")
        q_mvar = float(q_raw) if q_raw is not None else None

        ctx.prev_result = ctx.session.last_result
        if _is_llm_only():
            _modify_load_no_solve(ctx.net, bus_id=bus_id, p_mw=p_mw, q_mvar=q_mvar)
            res = _run_pf_with_backend()
        else:
            res = _modify_bus_load(ctx.net, bus_id=bus_id, p_mw=p_mw, q_mvar=q_mvar, config=ctx.solver_config)
        if isinstance(res, dict) and res.get("error"):
            return res
        ctx.session.last_result = res

        ctx.session.modification_log.append(
            Modification(
                action="modify_load",
                description=f"Modify bus {bus_id} load to P={p_mw} MW" + (f", Q={q_mvar} Mvar" if q_mvar is not None else ""),
                parameters={"bus_id": bus_id, "p_mw": p_mw, "q_mvar": q_mvar},
            )
        )
        return res.model_dump()

    def disconnect_line(args: Mapping[str, Any]) -> Any:
        if ctx.net is None:
            return {"error": "Please load a test case first."}
        fb = int(args.get("from_bus"))
        tb = int(args.get("to_bus"))
        ctx.prev_result = ctx.session.last_result
        if _is_llm_only():
            _disconnect_line_no_solve(ctx.net, from_bus=fb, to_bus=tb)
            res = _run_pf_with_backend()
        else:
            res = _disconnect_line(ctx.net, from_bus=fb, to_bus=tb, config=ctx.solver_config)
        if isinstance(res, dict) and res.get("error"):
            return res
        ctx.session.last_result = res
        ctx.session.modification_log.append(
            Modification(action="disconnect_line", description=f"Disconnect branch bus {fb} - bus {tb}", parameters={"from_bus": fb, "to_bus": tb})
        )
        return res.model_dump()

    def reconnect_line(args: Mapping[str, Any]) -> Any:
        if ctx.net is None:
            return {"error": "Please load a test case first."}
        fb = int(args.get("from_bus"))
        tb = int(args.get("to_bus"))
        ctx.prev_result = ctx.session.last_result
        if _is_llm_only():
            _reconnect_line_no_solve(ctx.net, from_bus=fb, to_bus=tb)
            res = _run_pf_with_backend()
        else:
            res = _reconnect_line(ctx.net, from_bus=fb, to_bus=tb, config=ctx.solver_config)
        if isinstance(res, dict) and res.get("error"):
            return res
        ctx.session.last_result = res
        ctx.session.modification_log.append(
            Modification(action="reconnect_line", description=f"Reconnect branch bus {fb} - bus {tb}", parameters={"from_bus": fb, "to_bus": tb})
        )
        return res.model_dump()

    def get_status(_: Mapping[str, Any]) -> Any:
        if ctx.net is None:
            return {"active_case": None, "network_info": None, "last_result": None}
        info = _get_network_status(ctx.net)
        out: dict[str, Any] = {
            "active_case": ctx.session.active_case,
            "network_info": info.model_dump(),
            "has_last_result": ctx.session.last_result is not None,
        }
        if ctx.session.last_result is not None:
            r = ctx.session.last_result
            out["last_result_summary"] = {
                "converged": r.converged,
                "total_load_mw": r.total_load_mw,
                "total_generation_mw": r.total_generation_mw,
                "total_loss_mw": r.total_loss_mw,
                "n_voltage_violations": len(r.voltage_violations),
                "n_thermal_violations": len(r.thermal_violations),
                "solver_backend": r.solver_backend,
            }
        return out

    def get_most_loaded_branch(_: Mapping[str, Any]) -> Any:
        if ctx.net is None:
            return {"error": "Please load a test case first."}
        if ctx.session.last_result is None:
            return {"error": "Please run power flow first."}
        info = _get_most_loaded_branch(ctx.net)
        if info is None:
            return {"error": "No branch loading info available."}
        return info

    def run_n1_contingency(args: Mapping[str, Any]) -> Any:
        if _is_llm_only():
            return _llm_disabled()
        if ctx.net is None:
            return {"error": "Please load a test case first."}

        report = _run_n1_contingency(
            ctx.net,
            top_k=int(args.get("top_k", 5) or 5),
            criteria=str(args.get("criteria", "max_violations") or "max_violations"),
            max_candidates=int(args.get("max_candidates", 0) or 0),
            config=ctx.solver_config,
        )
        ctx.session.last_n1_report = report
        ctx.last_n1_report = report

        theme = "dark" if str(ctx.theme).lower().startswith("dark") else "light"
        fig_json = pio.to_json(make_n1_ranking(report, theme=theme, lang=_lang()), validate=False)
        return {"plot_type": "n1_ranking", "figure_json": fig_json, "n1_report": report.model_dump()}

    def generate_plot(args: Mapping[str, Any]) -> Any:
        if ctx.net is None or ctx.session.last_result is None:
            return {"error": "Please load case and run power flow first."}

        plot_type = str(args.get("plot_type"))
        theme = "dark" if str(ctx.theme).lower().startswith("dark") else "light"

        if ctx.cached_positions is None:
            ctx.cached_positions = _compute_layout(ctx.net, _build_graph(ctx.net))
        positions = ctx.cached_positions

        fig = None
        if plot_type == "voltage_heatmap":
            fig = make_voltage_heatmap(
                ctx.net,
                ctx.session.last_result,
                positions=positions,
                theme=theme,
                lang=_lang(),
            )
        elif plot_type == "flow_diagram":
            fig = make_flow_diagram(ctx.net, ctx.session.last_result, positions=positions, theme=theme, lang=_lang())
        elif plot_type == "violation_overview":
            fig = make_violation_overview(
                ctx.net,
                ctx.session.last_result,
                positions=positions,
                theme=theme,
                lang=_lang(),
            )
        elif plot_type == "comparison":
            if ctx.prev_result is None:
                return {"error": "No previous scenario to compare."}
            fig = make_comparison(
                ctx.net,
                ctx.prev_result,
                ctx.session.last_result,
                positions=positions,
                theme=theme,
                lang=_lang(),
            )
        else:
            return {"error": f"Unsupported plot_type: {plot_type}"}

        fig_json = pio.to_json(fig, validate=False)
        ctx.last_plot_json = fig_json
        ctx.last_plot_type = plot_type
        return {"plot_type": plot_type, "figure_json": fig_json}

    def recommend_remedial_actions(args: Mapping[str, Any]) -> Any:
        if _is_llm_only():
            return _llm_disabled()
        if ctx.net is None or ctx.session.last_result is None:
            return {"error": "Please load case and run power flow first."}

        plan = _recommend_remedial_actions(
            ctx.net,
            ctx.session.last_result,
            config=ctx.solver_config,
            max_actions=int(args.get("max_actions", 5) or 5),
            allow_load_shed=bool(args.get("allow_load_shed", True)),
            allow_voltage_control=bool(args.get("allow_voltage_control", True)),
        )
        ctx.session.last_remedial_plan = plan

        theme = "dark" if str(ctx.theme).lower().startswith("dark") else "light"
        fig_json = pio.to_json(make_remedial_ranking(plan, theme=theme, lang=_lang()), validate=False)

        extra_figures: list[dict[str, Any]] = []
        if bool(args.get("include_best_comparison", True)) and plan.actions and plan.actions[0].preview_result is not None:
            if ctx.cached_positions is None:
                ctx.cached_positions = _compute_layout(ctx.net, _build_graph(ctx.net))
            cmp_fig = make_comparison(
                ctx.net,
                ctx.session.last_result,
                plan.actions[0].preview_result,
                positions=ctx.cached_positions,
                theme=theme,
                lang=_lang(),
            )
            extra_figures.append(
                {
                    "plot_type": "comparison",
                    "figure_json": pio.to_json(cmp_fig, validate=False),
                    "title": ("Best remedial before/after" if _lang() == "en" else "最佳建议前后对比"),
                }
            )

        return {
            "plot_type": "remedial_ranking",
            "figure_json": fig_json,
            "remedial_plan": plan.model_dump(),
            "extra_figures": extra_figures,
        }

    def apply_remedial_action(args: Mapping[str, Any]) -> Any:
        if _is_llm_only():
            return _llm_disabled()
        if ctx.net is None or ctx.session.last_result is None:
            return {"error": "Please load case and run power flow first."}

        plan = ctx.session.last_remedial_plan
        if plan is None or not plan.actions:
            return {"error": "No remedial plan available. Call recommend_remedial_actions first."}

        raw_idx = int(args.get("action_index"))
        idx = raw_idx - 1 if raw_idx >= 1 else raw_idx
        if idx < 0 or idx >= len(plan.actions):
            return {"error": f"action_index out of range: 1..{len(plan.actions)}"}

        act = plan.actions[idx]
        if not bool(args.get("confirmed", False)):
            return {
                "need_confirmation": True,
                "action_index": idx + 1,
                "action": {
                    "action": act.action,
                    "description": act.description,
                    "parameters": act.parameters,
                    "predicted_risk": act.predicted_risk,
                    "risk_reduction": act.risk_reduction,
                },
                "message": "This will modify network and re-solve. Re-call with confirmed=true to proceed.",
            }

        ctx.prev_result = ctx.session.last_result
        new_res = _apply_remedial_action_inplace(ctx.net, act, config=ctx.solver_config)
        ctx.session.last_result = new_res
        ctx.session.modification_log.append(
            Modification(
                action="apply_remedial_action",
                description=f"Apply remedial action #{idx+1}: {act.description}",
                parameters={"action_index": idx + 1, "action": act.action, **(act.parameters or {})},
            )
        )
        ctx.session.last_remedial_plan = None

        theme = "dark" if str(ctx.theme).lower().startswith("dark") else "light"
        extra_figures: list[dict[str, Any]] = []
        try:
            if ctx.cached_positions is None:
                ctx.cached_positions = _compute_layout(ctx.net, _build_graph(ctx.net))
            cmp_fig = make_comparison(
                ctx.net,
                ctx.prev_result,
                new_res,
                positions=ctx.cached_positions,
                theme=theme,
                lang=_lang(),
            )
            extra_figures.append(
                {
                    "plot_type": "comparison",
                    "figure_json": pio.to_json(cmp_fig, validate=False),
                    "title": ("After apply" if _lang() == "en" else "应用后对比"),
                }
            )
        except Exception:
            pass

        return {
            "applied": True,
            "applied_action_index": idx + 1,
            "applied_action": {"action": act.action, "description": act.description, "parameters": act.parameters},
            "result": new_res.model_dump(),
            "extra_figures": extra_figures,
        }

    return ToolDispatcher(
        handlers={
            "load_case": load_case,
            "run_powerflow": run_powerflow,
            "modify_load": modify_load,
            "disconnect_line": disconnect_line,
            "reconnect_line": reconnect_line,
            "get_status": get_status,
            "get_most_loaded_branch": get_most_loaded_branch,
            "run_n1_contingency": run_n1_contingency,
            "recommend_remedial_actions": recommend_remedial_actions,
            "apply_remedial_action": apply_remedial_action,
            "generate_plot": generate_plot,
        }
    )
