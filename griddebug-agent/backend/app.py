import os
import re
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import pandas as pd
from typing import Optional, Dict, List, Any

import pandapower as pp
from scenarios.code_sandbox import execute_safely

from openai import OpenAI

from scenarios import (
    NonConvergenceScenarios,
    VoltageViolationScenarios,
    ThermalOverloadScenarios,
    ContingencyFailureScenarios,
    NormalScenarios,
)
from scenarios.base_scenarios import load_network
from agents.baseline import BaselineAgent
from agents.iterative_debugger import IterativeDebuggerAgent
from scenarios.nl_scenario_generator import NLScenarioGenerator

load_dotenv()

app = FastAPI(title="GridDebugAgent API")

# Allow frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------
#  LLM Client
# ---------------------

_openai_key = os.getenv("OPENAI_API_KEY", "")
if not _openai_key:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. "
        "Create a .env file in the backend directory with: OPENAI_API_KEY=sk-..."
    )
_llm_client = OpenAI(api_key=_openai_key)
_baseline_agent = BaselineAgent(llm_client=_llm_client)
_iterative_agent = IterativeDebuggerAgent(llm_client=_llm_client)
_nl_generator = NLScenarioGenerator(llm_client=_llm_client)


# ---------------------
#  Constants
# ---------------------

import inspect
import pandapower.networks as nw

def _get_available_networks() -> list[dict]:
    networks = []
    common_cases = ["case14", "case30", "case39", "case57", "case118", "case300"]

    # Priority defaults
    for name in common_cases:
        if hasattr(nw, name):
            networks.append({"id": name, "label": f"IEEE {name.replace('case', '')}-Bus"})

    # Add the rest of the zero-arg functions from pandapower.networks
    for name, obj in inspect.getmembers(nw):
        if inspect.isfunction(obj) and not name.startswith('_') and name not in common_cases:
            sig = inspect.signature(obj)
            has_required = any(
                p.default == inspect.Parameter.empty
                and p.kind in [inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY]
                for p in sig.parameters.values()
            )
            if not has_required:
                networks.append({"id": name, "label": name})
    return networks

NETWORKS = _get_available_networks()

SCENARIO_FACTORIES = {
    "nonconvergence": NonConvergenceScenarios,
    "voltage":        VoltageViolationScenarios,
    "thermal":        ThermalOverloadScenarios,
    "contingency":    ContingencyFailureScenarios,
    "normal":         NormalScenarios,
}

SCENARIOS = [
    # Normal Operation
    {"id": "normal_operation",              "label": "Normal Operation (Baseline)",          "category": "normal"},
    # Non-convergence
    {"id": "extreme_load_scaling",          "label": "Extreme Load Scaling (20×)",           "category": "nonconvergence"},
    {"id": "all_generators_removed",        "label": "All Generators Removed",               "category": "nonconvergence"},
    {"id": "near_zero_impedance",           "label": "Near-Zero Impedance Line",             "category": "nonconvergence"},
    {"id": "disconnected_subnetwork",       "label": "Disconnected Sub-Network",             "category": "nonconvergence"},
    # Voltage violations
    {"id": "heavy_loading_undervoltage",    "label": "Heavy Loading Under-Voltage (3×)",     "category": "voltage"},
    {"id": "excess_generation_overvoltage", "label": "Excess Generation Over-Voltage",       "category": "voltage"},
    {"id": "reactive_imbalance",            "label": "Reactive Power Imbalance",             "category": "voltage"},
    # Thermal overloads
    {"id": "concentrated_loading",          "label": "Concentrated Loading on Weak Bus",     "category": "thermal"},
    {"id": "reduced_thermal_limits",        "label": "Reduced Thermal Limits (30%)",         "category": "thermal"},
    {"id": "topology_redirection",          "label": "Topology Change Flow Redirection",     "category": "thermal"},
    # Contingency
    {"id": "line_contingency_overload",     "label": "N-1 Line Contingency Overload",        "category": "contingency"},
    {"id": "trafo_contingency_voltage",     "label": "N-1 Trafo Contingency Voltage",        "category": "contingency"},
]


# ---------------------
#  Helpers
# ---------------------

def _find_and_apply_scenario(scenario_id: str, network: str):
    """
    Instantiate the matching scenario, apply it, and return
    (scenario_object, ground_truth_result).
    """
    if scenario_id == "nl_generated":
        scenario_id = "normal_operation"

    entry = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if entry is None:
        raise HTTPException(404, f"Unknown scenario: {scenario_id}")

    factory = SCENARIO_FACTORIES[entry["category"]]
    all_scenarios = factory.all_scenarios(network)

    for sc in all_scenarios:
        result = sc.apply()
        if result.scenario_name == scenario_id:
            return sc, result

    raise HTTPException(404, f"Scenario '{scenario_id}' not found in factory")


def _extract_section_raw(report: str, section_name: str) -> str:
    """Extract raw text of a section from LLM report (for JSON parsing)."""
    lines = report.split("\n")
    section_lower = section_name.lower().replace(" ", "").replace("_", "")
    known_headers = ["rootcauses", "affectedcomponents", "correctiveactions", "confidenceassessment"]

    in_section = False
    captured_lines = []

    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower().replace(" ", "").replace("_", "")

        # Check if this line is ANY header
        is_any_header = False
        for h in known_headers:
            cleaned_line = re.sub(r'^[\s#*\-\d.]+', '', line_lower).strip()
            if cleaned_line.startswith(h):
                is_any_header = True
                break

        if is_any_header:
            cleaned_line = re.sub(r'^[\s#*\-\d.]+', '', line_lower).strip()
            if cleaned_line.startswith(section_lower):
                in_section = True
            else:
                in_section = False
        elif in_section:
            captured_lines.append(line)

    return "\n".join(captured_lines)


def _parse_llm_report(report: str) -> dict:
    """
    Parse LLM markdown report into rootCauses, affectedComponents, correctiveActions.
    Tries to be robust to:
      - Sections appearing on the same line (no newlines)
      - Bulleted lists (-, *) and numbered lists (1., 2., ...)
      - Various markdown headers (##, **, etc.)
    """
    result = {"rootCauses": [], "affectedComponents": [], "correctiveActions": []}

    def _normalize_block(text: str) -> str:
        text = text.strip()
        # Convert " - " into real bullets on new lines
        text = re.sub(r"\s-\s", r"\n- ", text)
        # Convert " 1. " into numbered items on new lines
        text = re.sub(r"\s(\d+)\.\s+", r"\n\1. ", text)
        return text.strip()

    def _extract_items(block: str) -> list[str]:
        items: list[str] = []
        for line in _normalize_block(block).split("\n"):
            line = line.strip()
            # Remove leading/trailing bold markers
            if line.startswith("**") and line.endswith("**"):
                line = line[2:-2].strip()
            if not line:
                continue
            if line.startswith(("-", "*")):
                item = line.lstrip("-*").strip()
                if item:
                    items.append(item)
                continue
            if re.match(r"^\d+\.\s+", line):
                item = re.sub(r"^\d+\.\s+", "", line).strip()
                if item:
                    items.append(item)
                continue
            items.append(line)
        if not items and block.strip():
            return [block.strip()]
        return items

    def extract_section_items(text: str, section: str) -> list[str]:
        lines = text.split("\n")
        in_section = False
        captured_lines = []

        section_lower = section.lower()
        known_headers = ["root causes", "affected components", "corrective actions", "reasoning trace"]

        for line in lines:
            line_lower = line.lower()

            # Check if this line is ANY header
            is_any_header = False
            for h in known_headers:
                # Look for header near the start of the line, ignoring markdown markers
                cleaned_line = re.sub(r'^[\s#*\-\d.]+', '', line_lower).strip()
                if cleaned_line.startswith(h):
                    is_any_header = True
                    break

            if is_any_header:
                cleaned_line = re.sub(r'^[\s#*\-\d.]+', '', line_lower).strip()
                if cleaned_line.startswith(section_lower):
                    in_section = True
                    # Check if there's content on the same line after a colon or **
                    if ":" in line:
                        content_after_colon = line.split(":", 1)[1].strip()
                        if content_after_colon:
                            # if it ends with bold marker, strip it
                            if content_after_colon.endswith("**"):
                                content_after_colon = content_after_colon[:-2]
                            captured_lines.append(content_after_colon)
                else:
                    in_section = False
            elif in_section:
                captured_lines.append(line)

        return _extract_items("\n".join(captured_lines))

    result["rootCauses"] = extract_section_items(report, "Root Causes")
    result["affectedComponents"] = extract_section_items(report, "Affected Components")
    result["correctiveActions"] = extract_section_items(report, "Corrective Actions")

    # Filter out JSON blocks and fragments from affectedComponents (JSON is parsed separately)
    def _is_json_fragment(s: str) -> bool:
        s = s.strip()
        if not s:
            return True
        # JSON object start/end
        if s.startswith("{") or s.startswith("}") or s == "}":
            return True
        # Code fence
        if s.startswith("```"):
            return True
        # JSON key-value pairs like "bus": [], "line": [9, 28],
        if re.match(r'^"?(bus|line|load|gen|trafo|ext_grid)"?\s*:', s):
            return True
        return False

    result["affectedComponents"] = [
        item for item in result["affectedComponents"]
        if not _is_json_fragment(item)
    ]

    return result


def _parse_affected_component(text: str) -> dict | None:
    """
    Parse LLM component strings like:
    - "Bus 3" -> {"type": "bus", "index": 3}
    - "Line 5-7" -> {"type": "line", "index": 5}
    - "Load 0-41" -> {"type": "load", "index": 0}
    - "Generator 2" -> {"type": "gen", "index": 2}
    - "Transformer 1" -> {"type": "trafo", "index": 1}
    """
    text = text.strip().lower()

    patterns = [
        (r'bus\s*(\d+)', 'bus'),
        (r'line\s*(\d+)(?:\s*[-–]\s*\d+)?', 'line'),
        (r'load\s*(\d+)(?:\s*[-–]\s*\d+)?', 'load'),
        (r'gen(?:erator)?\s*(\d+)', 'gen'),
        (r'trafo(?:rmer)?\s*(\d+)', 'trafo'),
        (r'transformer\s*(\d+)', 'trafo'),
        (r'ext(?:ernal)?\s*grid\s*(\d+)', 'ext_grid'),
    ]

    for pattern, comp_type in patterns:
        match = re.search(pattern, text)
        if match:
            return {"type": comp_type, "index": int(match.group(1))}

    return None


def _extract_json_from_text(text: str) -> dict | None:
    """
    Extract JSON object from text, looking for ```json blocks or raw JSON.
    Returns parsed dict or None if not found/invalid.
    """
    # Try to find ```json ... ``` block
    json_block_match = re.search(r'```json\s*(\{[^`]+\})\s*```', text, re.DOTALL)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    json_match = re.search(r'\{[^{}]*"(?:bus|line|load|gen|trafo|ext_grid)"[^{}]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _parse_affected_components_list(components: list[str], full_text: str = "") -> dict[str, list[int]]:
    """
    Parse list of LLM component strings into structured format.
    First tries to extract JSON from the text, then falls back to regex parsing.
    Returns: {"bus": [3, 5], "line": [1, 2], ...}
    """
    result: dict[str, list[int]] = {}

    # First, try to extract JSON from the full affected components text
    combined_text = full_text or " ".join(components)
    json_data = _extract_json_from_text(combined_text)

    if json_data:
        # Parse JSON format
        valid_types = {"bus", "line", "load", "gen", "trafo", "ext_grid"}
        for comp_type, value in json_data.items():
            if comp_type not in valid_types:
                continue
            if value == "all":
                result[comp_type] = ["all"]
            elif isinstance(value, list):
                indices = [int(i) for i in value if isinstance(i, (int, float)) or (isinstance(i, str) and i.isdigit())]
                if indices:
                    result[comp_type] = indices
        return result

    # Fall back to regex parsing
    for comp_text in components:
        parsed = _parse_affected_component(comp_text)
        if parsed:
            comp_type = parsed["type"]
            comp_index = parsed["index"]
            if comp_type not in result:
                result[comp_type] = []
            if comp_index not in result[comp_type]:
                result[comp_type].append(comp_index)

    return result


def _build_pipeline_result(
    report: str,
    analysis_status: str = "success",
    structured_output: dict | None = None
) -> dict:
    """
    Build pipeline result with analysisStatus and parsed fields.

    If structured_output is provided (from function calling), use it directly.
    Otherwise, fall back to parsing the report text.
    """
    if structured_output:
        # Use structured output directly (from function calling)
        affected = structured_output.get("affected_components", {})
        # Build prose descriptions for display
        affected_prose = []
        component_names = {"bus": "Buses", "line": "Lines", "load": "Loads",
                          "gen": "Generators", "trafo": "Transformers", "ext_grid": "External Grids"}
        for comp_type, display_name in component_names.items():
            indices = affected.get(comp_type, [])
            if indices:
                affected_prose.append(f"{display_name}: {', '.join(map(str, indices))}")

        return {
            "analysisStatus": analysis_status,
            "rootCauses": structured_output.get("root_causes", []),
            "affectedComponents": affected_prose,
            "correctiveActions": structured_output.get("corrective_actions", []),
            "parsedAffectedComponents": affected,
            "rawResult": report,
        }

    # Fall back to parsing report text
    parsed = _parse_llm_report(report)
    affected_section_raw = _extract_section_raw(report, "Affected Components")
    parsed_components = _parse_affected_components_list(
        parsed["affectedComponents"],
        full_text=affected_section_raw
    )
    return {
        "analysisStatus": analysis_status,
        "rootCauses": parsed["rootCauses"],
        "affectedComponents": parsed["affectedComponents"],
        "correctiveActions": parsed["correctiveActions"],
        "parsedAffectedComponents": parsed_components,
        "rawResult": report,
    }


def _format_reasoning_trace(tool_calls: list, final_report_snippet: str | None = None, max_result_len: int = 400) -> str:
    """Build a human-readable full reasoning trace for the agentic pipeline."""
    lines = [
        "=== Agentic reasoning trace ===",
        "Input: evidence text + triggered rules + failure_category (from Preprocessor).",
        "",
    ]
    for i, tc in enumerate(tool_calls, 1):
        tool = tc.get("tool", "?")
        args = tc.get("args") or {}
        result = tc.get("result")
        it = tc.get("iteration", i - 1)
        args_str = json.dumps(args, default=str) if args else ""
        if isinstance(result, dict):
            result_str = json.dumps(result, default=str)
        else:
            result_str = str(result)
        if len(result_str) > max_result_len:
            result_str = result_str[:max_result_len] + "..."
        lines.append(f"Step {i} (iteration {it}): Called {tool}({args_str})")
        lines.append(f"  → result: {result_str}")
        lines.append("")
    lines.append("Final step: Produced FINAL REPORT (parsed into root causes, affected components, corrective actions).")
    if final_report_snippet:
        snippet = (final_report_snippet[:800] + "...") if len(final_report_snippet) > 800 else final_report_snippet
        lines.append("")
        lines.append("--- Report snippet ---")
        lines.append(snippet)
    return "\n".join(lines)


def _evaluate_reasoning_quality(
    tool_calls: list,
    root_causes: list,
    affected_components: list,
    corrective_actions: list,
) -> dict:
    """
    Heuristic checks: does the agent's tool usage support what it claimed in the report?
    Returns { "checks": [ {"id", "passed", "message"} ], "summary": "x/y passed" }.
    """
    report_text = " ".join(root_causes + affected_components + corrective_actions).lower()
    tools_used = [tc.get("tool", "") for tc in tool_calls]
    checks = []

    # 1. Agent used at least one tool (gathered evidence)
    used_tools = len(tool_calls) > 0
    checks.append({
        "id": "used_tools",
        "passed": used_tools,
        "message": "Agent called at least one tool to gather evidence." if used_tools else "Agent produced report without calling any tools (no tool-based evidence).",
    })

    # 2. If report mentions overload/loading/thermal → expect relevant tools
    overload_keywords = ["overload", "loading", "thermal", "line loading", "congestion"]
    mentions_overload = any(k in report_text for k in overload_keywords)
    overload_tools = ["check_overloads", "get_loading_profile", "run_full_diagnostics", "run_power_flow", "run_dc_power_flow"]
    has_overload_evidence = any(t in tools_used for t in overload_tools)
    if mentions_overload:
        checks.append({
            "id": "evidence_for_overload",
            "passed": has_overload_evidence,
            "message": "Report mentions overload/loading; agent used overload/flow/diagnostic tools." if has_overload_evidence else "Report mentions overload/loading but agent did not call overload or power-flow tools.",
        })

    # 3. If report mentions voltage → expect voltage-related tools
    voltage_keywords = ["voltage", "vm_pu", "violation", "undervoltage", "overvoltage"]
    mentions_voltage = any(k in report_text for k in voltage_keywords)
    voltage_tools = ["check_voltage_violations", "get_voltage_profile"]
    has_voltage_evidence = any(t in tools_used for t in voltage_tools)
    if mentions_voltage:
        checks.append({
            "id": "evidence_for_voltage",
            "passed": has_voltage_evidence,
            "message": "Report mentions voltage; agent used voltage-related tools." if has_voltage_evidence else "Report mentions voltage but agent did not call voltage tools.",
        })

    # 4. If report mentions balance/generation/load/convergence → expect balance or flow tools
    balance_keywords = ["balance", "generation", "load", "convergence", "imbalance", "gen", "demand"]
    mentions_balance = any(k in report_text for k in balance_keywords)
    balance_tools = ["get_power_balance", "get_network_summary", "run_power_flow", "run_full_diagnostics"]
    has_balance_evidence = any(t in tools_used for t in balance_tools)
    if mentions_balance:
        checks.append({
            "id": "evidence_for_balance",
            "passed": has_balance_evidence,
            "message": "Report mentions balance/load/gen; agent used balance or flow tools." if has_balance_evidence else "Report mentions balance/load/gen but agent did not call power-balance or flow tools.",
        })

    # 5. Diagnostic order: power flow before overload/voltage checks (if those were used)
    flow_tools = ["run_power_flow", "run_dc_power_flow", "run_full_diagnostics"]
    diag_tools = ["check_overloads", "check_voltage_violations"]
    flow_indices = [i for i, t in enumerate(tools_used) if t in flow_tools]
    diag_indices = [i for i, t in enumerate(tools_used) if t in diag_tools]
    order_ok = True
    if diag_indices and flow_indices:
        order_ok = min(flow_indices) < max(diag_indices)
    checks.append({
        "id": "reasonable_order",
        "passed": order_ok,
        "message": "Power flow / full diagnostics ran before overload/voltage checks (data before diagnosis)." if order_ok else "Overload/voltage checks ran but no prior power-flow/diagnostics call; consider running flow first.",
    })

    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    return {
        "checks": checks,
        "summary": f"{passed}/{total} checks passed",
        "passedCount": passed,
        "totalCount": total,
    }


def _generate_bus_coordinates(net: pp.pandapowerNet) -> dict[int, dict[str, float]]:
    """
    Generate hierarchical layout coordinates for buses using BFS from slack bus.
    Returns {bus_idx: {"x": float, "y": float}}
    """
    from collections import deque

    coords: dict[int, dict[str, float]] = {}
    bus_indices = list(net.bus.index)
    if not bus_indices:
        return coords

    # Build adjacency list from lines and transformers
    adjacency: dict[int, list[int]] = {b: [] for b in bus_indices}

    for _, line in net.line.iterrows():
        from_bus, to_bus = int(line["from_bus"]), int(line["to_bus"])
        if from_bus in adjacency and to_bus in adjacency:
            adjacency[from_bus].append(to_bus)
            adjacency[to_bus].append(from_bus)

    if hasattr(net, 'trafo') and not net.trafo.empty:
        for _, trafo in net.trafo.iterrows():
            hv_bus, lv_bus = int(trafo["hv_bus"]), int(trafo["lv_bus"])
            if hv_bus in adjacency and lv_bus in adjacency:
                adjacency[hv_bus].append(lv_bus)
                adjacency[lv_bus].append(hv_bus)

    # Find starting bus (prefer external grid, then first generator, then bus 0)
    start_bus = bus_indices[0]
    if hasattr(net, 'ext_grid') and not net.ext_grid.empty:
        start_bus = int(net.ext_grid.iloc[0]["bus"])
    elif hasattr(net, 'gen') and not net.gen.empty:
        start_bus = int(net.gen.iloc[0]["bus"])

    # BFS to assign layers
    visited: set[int] = set()
    layers: dict[int, list[int]] = {}
    queue: deque[tuple[int, int]] = deque([(start_bus, 0)])
    visited.add(start_bus)

    while queue:
        bus, layer = queue.popleft()
        layers.setdefault(layer, []).append(bus)
        for neighbor in adjacency[bus]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, layer + 1))

    # Handle disconnected buses
    for bus in bus_indices:
        if bus not in visited:
            max_layer = max(layers.keys()) + 1 if layers else 0
            layers.setdefault(max_layer, []).append(bus)

    # Assign coordinates: x = layer, y = position within layer
    x_spacing = 150
    y_spacing = 100

    for layer, buses in layers.items():
        for i, bus in enumerate(buses):
            y_offset = (i - len(buses) / 2) * y_spacing
            coords[bus] = {"x": float(layer * x_spacing), "y": float(y_offset)}

    return coords


def _serialize_network_state(
    net: pp.pandapowerNet,
    run_pf: bool = True,
    affected_components: dict | None = None
) -> dict:
    """
    Serialize a pandapower network to a dict for frontend visualization.
    Runs power flow if requested to populate res_bus/res_line.
    Expands "all" markers in affected_components to actual indices.
    """
    converged = False
    if run_pf:
        try:
            pp.runpp(net)
            converged = getattr(net, "converged", False)
        except Exception:
            pass
    else:
        converged = getattr(net, "converged", False)

    bus_coords = _generate_bus_coordinates(net)

    # Expand "all" markers in affected_components to actual indices
    expanded_affected = {}
    if affected_components:
        component_tables = {
            "bus": net.bus,
            "line": net.line,
            "load": net.load if hasattr(net, "load") else None,
            "gen": net.gen if hasattr(net, "gen") else None,
            "trafo": net.trafo if hasattr(net, "trafo") else None,
            "ext_grid": net.ext_grid if hasattr(net, "ext_grid") else None,
        }
        for comp_type, indices in affected_components.items():
            if indices == ["all"] or indices == "all":
                table = component_tables.get(comp_type)
                if table is not None and not table.empty:
                    expanded_affected[comp_type] = list(table.index.astype(int))
                else:
                    expanded_affected[comp_type] = []
            else:
                expanded_affected[comp_type] = indices

    return {
        "bus": json.loads(net.bus.to_json(orient="index")),
        "line": json.loads(net.line.to_json(orient="index")),
        "load": json.loads(net.load.to_json(orient="index")) if getattr(net, "load", None) is not None and not net.load.empty else {},
        "gen": json.loads(net.gen.to_json(orient="index")) if getattr(net, "gen", None) is not None and not net.gen.empty else {},
        "trafo": json.loads(net.trafo.to_json(orient="index")) if getattr(net, "trafo", None) is not None and not net.trafo.empty else {},
        "ext_grid": json.loads(net.ext_grid.to_json(orient="index")) if getattr(net, "ext_grid", None) is not None and not net.ext_grid.empty else {},
        "res_bus": json.loads(net.res_bus.to_json(orient="index")) if getattr(net, "res_bus", None) is not None and not net.res_bus.empty else {},
        "res_line": json.loads(net.res_line.to_json(orient="index")) if getattr(net, "res_line", None) is not None and not net.res_line.empty else {},
        "bus_coords": bus_coords,
        "affected_components": expanded_affected,
        "converged": converged,
    }


# ---------------------
#  Models
# ---------------------

class DiagnoseRequest(BaseModel):
    """Request body for the /diagnose endpoint."""
    network: str = "case14"
    scenario: str
    pipeline: str = "baseline"              # "baseline" or "agentic"
    query: Optional[str] = None             # optional user/benchmark query (e.g. paper queries)


class DiagnoseResult(BaseModel):
    """Response body returned by the /diagnose endpoint."""
    baseline: dict
    agentic: dict


class DiagnoseNLRequest(BaseModel):
    """Request body for the /diagnose_nl endpoint."""
    network: str = "case14"
    description: str


class OverrideState(BaseModel):
    """State of manual network overrides from the frontend control board."""
    globalLoadScale: float = 1.0  # multiplier for all loads
    # In-service state maps (boolean only)
    lineStates: Dict[int, bool] = {}
    trafoStates: Dict[int, bool] = {}
    genStates: Dict[int, bool] = {}
    loadStates: Dict[int, bool] = {}
    extGridStates: Dict[int, bool] = {}
    # Value overrides (numeric properties)
    loadValues: Dict[int, Dict[str, float]] = {}   # e.g., {idx: {"p_mw": 50.0, "q_mvar": 20.0}}
    genValues: Dict[int, Dict[str, float]] = {}    # e.g., {idx: {"p_mw": 100.0, "vm_pu": 1.02}}
    extGridValues: Dict[int, Dict[str, float]] = {} # e.g., {idx: {"vm_pu": 1.02}}


def _apply_overrides(net: pp.pandapowerNet, overrides: OverrideState) -> None:
    """Apply manual overrides to a pandapower network (mutates net in place)."""
    # Global load scale
    if overrides.globalLoadScale != 1.0:
        if not net.load.empty and "p_mw" in net.load.columns:
            net.load["p_mw"] *= overrides.globalLoadScale
        if not net.load.empty and "q_mvar" in net.load.columns:
            net.load["q_mvar"] *= overrides.globalLoadScale

    # Line states (in_service)
    for idx_str, in_service in overrides.lineStates.items():
        idx = int(idx_str)
        if idx in net.line.index:
            net.line.at[idx, "in_service"] = in_service

    # Trafo states (in_service)
    for idx_str, in_service in overrides.trafoStates.items():
        idx = int(idx_str)
        if idx in net.trafo.index:
            net.trafo.at[idx, "in_service"] = in_service

    # Gen states (in_service)
    for idx_str, in_service in overrides.genStates.items():
        idx = int(idx_str)
        if idx in net.gen.index:
            net.gen.at[idx, "in_service"] = in_service

    # Gen values (p_mw, vm_pu)
    for idx_str, values in overrides.genValues.items():
        idx = int(idx_str)
        if idx in net.gen.index:
            if "p_mw" in values:
                net.gen.at[idx, "p_mw"] = values["p_mw"]
            if "vm_pu" in values:
                net.gen.at[idx, "vm_pu"] = values["vm_pu"]

    # Load states (in_service)
    for idx_str, in_service in overrides.loadStates.items():
        idx = int(idx_str)
        if idx in net.load.index:
            net.load.at[idx, "in_service"] = in_service

    # Load values (p_mw, q_mvar)
    for idx_str, values in overrides.loadValues.items():
        idx = int(idx_str)
        if idx in net.load.index:
            if "p_mw" in values:
                net.load.at[idx, "p_mw"] = values["p_mw"]
            if "q_mvar" in values:
                net.load.at[idx, "q_mvar"] = values["q_mvar"]

    # Ext grid states (in_service)
    for idx_str, in_service in overrides.extGridStates.items():
        idx = int(idx_str)
        if getattr(net, "ext_grid", None) is not None and idx in net.ext_grid.index:
            net.ext_grid.at[idx, "in_service"] = in_service

    # Ext grid values (vm_pu)
    for idx_str, values in overrides.extGridValues.items():
        idx = int(idx_str)
        if getattr(net, "ext_grid", None) is not None and idx in net.ext_grid.index:
            if "vm_pu" in values:
                net.ext_grid.at[idx, "vm_pu"] = values["vm_pu"]


class SimulateOverridesRequest(BaseModel):
    """Request body for testing manual overrides on an existing scenario."""
    network: str = "case14"
    scenario: str
    generatedCode: Optional[str] = None
    overrides: OverrideState
    llmAffectedComponents: Optional[Dict[str, Any]] = None  # Can be List[int] or ["all"]


class NetworkStateRequest(BaseModel):
    """Request body to fetch the raw components of a network, potentially with NL code."""
    network: str = "case14"
    scenario: str
    generatedCode: Optional[str] = None
    llmAffectedComponents: Optional[Dict[str, Any]] = None  # Can be List[int] or ["all"]


class ReDiagnoseRequest(BaseModel):
    """Request body for re-diagnosing with overrides applied."""
    network: str = "case14"
    scenario: str
    generatedCode: Optional[str] = None
    overrides: OverrideState



# ---------------------
#  GET  /networks
# ---------------------

@app.get("/networks")
def get_networks():
    """Return the list of available IEEE test networks for the dropdown."""
    return {"networks": NETWORKS}


# ---------------------
#  GET  /scenarios
# ---------------------

@app.get("/scenarios")
def get_scenarios():
    """Return the list of available failure scenarios for the dropdown."""
    return {"scenarios": SCENARIOS}




# ---------------------
#  POST /api/network_state
# ---------------------

@app.post("/api/network_state")
def get_network_state(req: NetworkStateRequest):
    """
    Return the raw network components data (buses, lines, generators)
    for a specific scenario (or generated NLP code).
    """
    # Handle NL-generated scenarios specially (not in SCENARIOS list)
    if req.scenario == "nl_generated" or req.scenario is None:
        net = load_network(req.network)
    else:
        scenario_obj, _ = _find_and_apply_scenario(req.scenario, req.network)
        net = scenario_obj.net

    # If it's an NLP-generated scenario, apply the generated code
    if req.generatedCode:
        execute_safely(req.generatedCode, net, timeout=5)

    # Use _serialize_network_state which handles "all" expansion
    affected_components = req.llmAffectedComponents or {}
    return _serialize_network_state(net, run_pf=True, affected_components=affected_components)

# ---------------------
#  POST /api/simulate_overrides
# ---------------------

@app.post("/api/simulate_overrides")
def run_simulate_overrides(req: SimulateOverridesRequest):
    """
    Apply manual user overrides (sliders/toggles) to a base network scenario,
    run the power flow, and return the updated network state.
    """
    # Handle NL-generated scenarios specially (not in SCENARIOS list)
    if req.scenario == "nl_generated" or req.scenario is None:
        net = load_network(req.network)
    else:
        scenario_obj, _ = _find_and_apply_scenario(req.scenario, req.network)
        net = scenario_obj.net

    if req.generatedCode:
        execute_safely(req.generatedCode, net, timeout=5)

    # Apply manual overrides using helper
    _apply_overrides(net, req.overrides)

    # Use _serialize_network_state which handles "all" expansion
    affected_components = req.llmAffectedComponents or {}
    return _serialize_network_state(net, run_pf=True, affected_components=affected_components)


# ---------------------
#  POST /api/rediagnose
# ---------------------

@app.post("/api/rediagnose")
def run_rediagnose(req: ReDiagnoseRequest):
    """
    Re-run LLM diagnosis on a network with manual overrides applied.
    Returns same structure as /diagnose.
    """
    print(f"[REDIAGNOSE] Received overrides: {req.overrides}")
    # Load base network
    if req.scenario == "nl_generated" or req.scenario is None:
        net = load_network(req.network)
    else:
        scenario_obj, _ = _find_and_apply_scenario(req.scenario, req.network)
        net = scenario_obj.net

    # Apply generated code if present
    if req.generatedCode:
        execute_safely(req.generatedCode, net, timeout=5)

    # Apply manual overrides using helper
    _apply_overrides(net, req.overrides)

    # Debug: show gen state after overrides
    print(f"[REDIAGNOSE] Gen table after overrides:\n{net.gen[['bus', 'p_mw', 'vm_pu', 'in_service']]}")

    # Run power flow
    try:
        pp.runpp(net)
        print(f"[REDIAGNOSE] Power flow converged: {net.converged}")
    except Exception as e:
        print(f"[REDIAGNOSE] Power flow failed: {e}")

    # Run both diagnosis pipelines
    baseline_result = _baseline_agent.diagnose(net, network_name=req.network)
    baseline_report = baseline_result["response"]
    baseline_structured = baseline_result.get("structured_output")
    baseline_status = "success" if not baseline_report.startswith("LLM call failed") else "error"
    baseline = _build_pipeline_result(baseline_report, baseline_status, baseline_structured)

    # Use iterative debugger for agentic tab
    try:
        import copy
        net_iter = copy.deepcopy(net)
        # Capture before state (broken network)
        before_state = _serialize_network_state(net_iter, run_pf=False)
        before_state["affected_components"] = baseline.get("parsedAffectedComponents", {})
        iter_result = _iterative_agent.diagnose(net_iter, network_name=req.network)
        # Capture after state (fixed network)
        after_state = _serialize_network_state(net_iter, run_pf=False)
        iter_report = iter_result["response"]
        iter_status = "success"
        if iter_report.startswith("Agent loop error") or iter_report.startswith("LLM call failed"):
            iter_status = "error"
        agentic = _build_pipeline_result(iter_report, iter_status)
        fix_history = iter_result.get("fix_history", [])
        agentic["fixHistory"] = fix_history
        agentic["finalConverged"] = iter_result.get("final_converged", False)
        agentic["iterationsUsed"] = iter_result.get("iterations_used", 0)
        agentic["toolCalls"] = fix_history
        # New structured fields
        agentic["initialDiagnosis"] = iter_result.get("initial_diagnosis", {})
        agentic["agentActions"] = iter_result.get("agent_actions", [])
        agentic["finalState"] = iter_result.get("final_state", {})
        # Before/After network states for visualization
        agentic["beforeState"] = before_state
        agentic["afterState"] = after_state
        agentic["querySummary"] = iter_result.get("query_summary")
    except Exception as e:
        print(f"[REDIAGNOSE] Agentic error: {e}")
        agentic = {
            "analysisStatus": "error",
            "rootCauses": [],
            "affectedComponents": [],
            "correctiveActions": [],
            "parsedAffectedComponents": {},
            "fixHistory": [],
            "finalConverged": False,
            "toolCalls": [],
            "initialDiagnosis": {},
            "agentActions": [],
            "finalState": {},
            "beforeState": {},
            "afterState": {},
        }

    # Serialize network state with overrides applied for frontend visualization
    # Use parsed affected components from baseline result for highlighting
    affected_components = baseline.get("parsedAffectedComponents", {})
    network_state = _serialize_network_state(net, run_pf=False, affected_components=affected_components)

    return {"baseline": baseline, "agentic": agentic, "networkState": network_state}


# ---------------------
#  POST /diagnose
# ---------------------

@app.post("/diagnose", response_model=DiagnoseResult)
def run_diagnose(req: DiagnoseRequest):
    """
    Run the selected scenario on the chosen network through both
    baseline and agentic pipelines, returning structured diagnosis results.
    """
    # Validate network
    valid_networks = [n["id"] for n in NETWORKS]
    if req.network not in valid_networks:
        raise HTTPException(400, f"Unknown network: {req.network}. Choose from {valid_networks}")

    # Apply the scenario to get a modified network
    scenario_obj, ground_truth = _find_and_apply_scenario(req.scenario, req.network)
    net = scenario_obj.net

    # Attempt power flow
    scenario_obj.run_pf()

    user_query = (req.query or "").strip() or ""

    # --- Baseline pipeline ---
    baseline_result = _baseline_agent.diagnose(net, network_name=req.network, user_query=user_query)
    baseline_report = baseline_result["response"]
    baseline_structured = baseline_result.get("structured_output")
    baseline_status = "success"
    if baseline_report.startswith("LLM call failed"):
        baseline_status = "error"
    baseline = _build_pipeline_result(baseline_report, baseline_status, baseline_structured)

    # --- Agentic pipeline (using iterative debugger) ---
    try:
        import copy
        net_iter = copy.deepcopy(net)
        # Capture before state (broken network)
        before_state = _serialize_network_state(net_iter, run_pf=False)
        before_state["affected_components"] = baseline.get("parsedAffectedComponents", {})
        iter_result = _iterative_agent.diagnose(net_iter, network_name=req.network)
        # Capture after state (fixed network)
        after_state = _serialize_network_state(net_iter, run_pf=False)
        iter_report = iter_result["response"]
        iter_status = "success"
        if iter_report.startswith("Agent loop error") or iter_report.startswith("LLM call failed"):
            iter_status = "error"
        agentic = _build_pipeline_result(iter_report, iter_status)
        fix_history = iter_result.get("fix_history", [])
        agentic["fixHistory"] = fix_history
        agentic["finalConverged"] = iter_result.get("final_converged", False)
        agentic["iterationsUsed"] = iter_result.get("iterations_used", 0)
        agentic["toolCalls"] = fix_history
        # New structured fields
        agentic["initialDiagnosis"] = iter_result.get("initial_diagnosis", {})
        agentic["agentActions"] = iter_result.get("agent_actions", [])
        agentic["finalState"] = iter_result.get("final_state", {})
        # Before/After network states for visualization
        agentic["beforeState"] = before_state
        agentic["afterState"] = after_state
        # Compute reasoning quality
        agentic["reasoningQuality"] = _evaluate_reasoning_quality(
            fix_history,
            agentic.get("rootCauses", []),
            agentic.get("affectedComponents", []),
            agentic.get("correctiveActions", []),
        )
    except Exception as e:
        agentic = {
            "analysisStatus": "error",
            "rootCauses": [],
            "affectedComponents": [],
            "correctiveActions": [],
            "toolCalls": [],
            "initialDiagnosis": {},
            "agentActions": [],
            "finalState": {},
            "beforeState": {},
            "afterState": {},
            "reasoningQuality": {"checks": [], "summary": f"Agent failed: {e}", "passedCount": 0, "totalCount": 0},
        }

    return DiagnoseResult(baseline=baseline, agentic=agentic)


# ---------------------
#  POST /diagnose_stream  (Server-Sent Events)
# ---------------------

from fastapi.responses import StreamingResponse
import asyncio, traceback

@app.post("/diagnose_stream")
async def run_diagnose_stream(req: DiagnoseRequest):
    """
    Same as /diagnose, but streams each pipeline result as a Server-Sent Event
    the moment it completes: baseline → agentic → done.
    Sync pipeline calls are offloaded to threads so the event loop can flush.
    """
    valid_networks = [n["id"] for n in NETWORKS]
    if req.network not in valid_networks:
        raise HTTPException(400, f"Unknown network: {req.network}")

    def _sse_event(event: str, data: dict) -> str:
        payload = json.dumps(data, default=str)
        return f"event: {event}\ndata: {payload}\n\n"

    # ---------- sync helpers (run in thread pool) ----------
    def _run_baseline(net, network_name, user_query):
        try:
            r = _baseline_agent.diagnose(net, network_name=network_name, user_query=user_query)
            report = r["response"]
            structured = r.get("structured_output")
            status = "error" if report.startswith("LLM call failed") else "success"
            return _build_pipeline_result(report, status, structured)
        except Exception as e:
            return {"analysisStatus": "error", "rootCauses": [], "affectedComponents": [],
                    "correctiveActions": [], "rawResult": str(e)}

    def _run_agentic(scenario_id, network_name, affected_components=None):
        """Run iterative debugger as the agentic pipeline."""
        try:
            s, _ = _find_and_apply_scenario(scenario_id, network_name)
            s.run_pf()
            # Capture before state (broken network)
            before_state = _serialize_network_state(s.net, run_pf=False)
            before_state["affected_components"] = affected_components or {}
            r = _iterative_agent.diagnose(s.net, network_name=network_name)
            # Capture after state (fixed network)
            after_state = _serialize_network_state(s.net, run_pf=False)
            report = r["response"]
            status = "success"
            if report.startswith("Agent loop error") or report.startswith("LLM call failed"):
                status = "error"
            out = _build_pipeline_result(report, status)
            fix_history = r.get("fix_history", [])
            out["fixHistory"] = fix_history
            out["finalConverged"] = r.get("final_converged", False)
            out["iterationsUsed"] = r.get("iterations_used", 0)
            out["toolCalls"] = fix_history
            # New structured fields
            out["initialDiagnosis"] = r.get("initial_diagnosis", {})
            out["agentActions"] = r.get("agent_actions", [])
            out["finalState"] = r.get("final_state", {})
            # Before/After network states for visualization
            out["beforeState"] = before_state
            out["afterState"] = after_state
            out["querySummary"] = r.get("query_summary")
            # Compute reasoning quality
            out["reasoningQuality"] = _evaluate_reasoning_quality(
                fix_history,
                out.get("rootCauses", []),
                out.get("affectedComponents", []),
                out.get("correctiveActions", []),
            )
            return out
        except Exception as e:
            print(f"[AGENTIC ERROR] {e}")
            traceback.print_exc()
            return {"analysisStatus": "error", "rootCauses": [], "affectedComponents": [],
                    "correctiveActions": [], "fixHistory": [], "finalConverged": False,
                    "iterationsUsed": 0, "toolCalls": [], "initialDiagnosis": {},
                    "agentActions": [], "finalState": {}, "beforeState": {}, "afterState": {}, "error": str(e)}

    async def event_generator():
        # Apply scenario
        scenario_obj, ground_truth = _find_and_apply_scenario(req.scenario, req.network)
        net = scenario_obj.net
        scenario_obj.run_pf()
        user_query = (req.query or "").strip() or ""

        # 1) Baseline — offload to thread so yield actually flushes
        baseline = await asyncio.to_thread(_run_baseline, net, req.network, user_query)
        yield _sse_event("baseline", baseline)

        # 2) Agentic (using iterative debugger)
        agentic = await asyncio.to_thread(_run_agentic, req.scenario, req.network, baseline.get("parsedAffectedComponents", {}))
        yield _sse_event("agentic", agentic)

        # 3) Done
        yield _sse_event("done", {"status": "complete"})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------
#  POST /diagnose_nl
# ---------------------

@app.post("/diagnose_nl")
def run_diagnose_nl(req: DiagnoseNLRequest):
    """
    Generate a failure scenario from a natural language description,
    then run it through the diagnosis pipelines.
    """
    # Validate network
    valid_networks = [n["id"] for n in NETWORKS]
    if req.network not in valid_networks:
        raise HTTPException(400, f"Unknown network: {req.network}. Choose from {valid_networks}")

    # Generate the scenario from NL
    gen_result = _nl_generator.generate(
        description=req.description,
        network_name=req.network,
    )

    if gen_result["generation_status"] != "success":
        return {
            "generationStatus": "error",
            "generationError": gen_result["error"],
            "generatedCode": gen_result.get("generated_code", ""),
            "generatedGroundTruth": None,
            "baseline": {
                "analysisStatus": "skipped",
                "rootCauses": [],
                "affectedComponents": [],
                "correctiveActions": [],
            },
            "agentic": {
                "analysisStatus": "skipped",
                "rootCauses": [],
                "affectedComponents": [],
                "correctiveActions": [],
            },
            "responseType": gen_result.get("response_type", "full_diagnosis"),
            "textAnswer": gen_result.get("text_answer", ""),
        }

    net = gen_result["net"]
    ground_truth = gen_result["ground_truth"]

    response_type = gen_result.get("response_type", "full_diagnosis")
    text_answer = gen_result.get("text_answer", "")

    # For text-only simple questions, skip power flow and diagnosis
    if response_type == "text_only":
        return {
            "generationStatus": "success",
            "generationError": None,
            "generatedCode": gen_result["generated_code"],
            "generatedGroundTruth": {
                "failureType": ground_truth.failure_type,
                "rootCauses": ground_truth.root_causes,
                "affectedComponents": ground_truth.affected_components,
                "knownFix": ground_truth.known_fix,
            },
            "baseline": {"analysisStatus": "skipped", "rootCauses": [], "affectedComponents": [], "correctiveActions": []},
            "agentic": {"analysisStatus": "skipped", "rootCauses": [], "affectedComponents": [], "correctiveActions": []},
            "responseType": response_type,
            "textAnswer": text_answer,
        }

    # For plot-only or full-diagnosis, we run power flow
    try:
        pp.runpp(net)
    except Exception:
        pass

    # For plot-only, skip the LLM diagnosis
    if response_type == "plot_only":
        return {
            "generationStatus": "success",
            "generationError": None,
            "generatedCode": gen_result["generated_code"],
            "generatedGroundTruth": {
                "failureType": ground_truth.failure_type,
                "rootCauses": ground_truth.root_causes,
                "affectedComponents": ground_truth.affected_components,
                "knownFix": ground_truth.known_fix,
            },
            "baseline": {"analysisStatus": "skipped", "rootCauses": [], "affectedComponents": [], "correctiveActions": []},
            "agentic": {"analysisStatus": "skipped", "rootCauses": [], "affectedComponents": [], "correctiveActions": []},
            "responseType": response_type,
            "textAnswer": text_answer,
        }

    # --- Baseline pipeline ---
    # Note: Don't pass req.description as user_query - it's the scenario description, not a query.
    # Passing it causes the LLM to use direct-answer format instead of diagnostic format.
    baseline_result = _baseline_agent.diagnose(net, network_name=req.network, user_query="")
    baseline_report = baseline_result["response"]
    baseline_structured = baseline_result.get("structured_output")
    baseline_status = "success"
    if baseline_report.startswith("LLM call failed"):
        baseline_status = "error"
    baseline = _build_pipeline_result(baseline_report, baseline_status, baseline_structured)

    # --- Agentic pipeline (iterative debugger) ---
    try:
        import copy
        net_iter = copy.deepcopy(net)
        # Capture before state (broken network)
        before_state = _serialize_network_state(net_iter, run_pf=False)
        before_state["affected_components"] = baseline.get("parsedAffectedComponents", {})
        agent_query = req.description if response_type == "direct_answer" else ""
        iter_result = _iterative_agent.diagnose(net_iter, network_name=req.network, user_query=agent_query)
        # Always generate query summary if user provided a description
        if not agent_query and req.description.strip() and "query_summary" not in iter_result:
            iter_result["query_summary"] = _iterative_agent._generate_query_summary(
                req.description, iter_result.get("fix_history", []), iter_result.get("response", "")
            )
        # Capture after state (fixed network)
        after_state = _serialize_network_state(net_iter, run_pf=False)
        iter_report = iter_result["response"]
        iter_status = "success"
        if iter_report.startswith("Agent loop error") or iter_report.startswith("LLM call failed"):
            iter_status = "error"
        agentic = _build_pipeline_result(iter_report, iter_status)
        fix_history = iter_result.get("fix_history", [])
        agentic["fixHistory"] = fix_history
        agentic["finalConverged"] = iter_result.get("final_converged", False)
        agentic["iterationsUsed"] = iter_result.get("iterations_used", 0)
        agentic["toolCalls"] = fix_history
        # New structured fields
        agentic["initialDiagnosis"] = iter_result.get("initial_diagnosis", {})
        agentic["agentActions"] = iter_result.get("agent_actions", [])
        agentic["finalState"] = iter_result.get("final_state", {})
        # Before/After network states for visualization
        agentic["beforeState"] = before_state
        agentic["afterState"] = after_state
        agentic["querySummary"] = iter_result.get("query_summary")
        agentic["reasoningQuality"] = _evaluate_reasoning_quality(
            fix_history,
            agentic.get("rootCauses", []),
            agentic.get("affectedComponents", []),
            agentic.get("correctiveActions", []),
        )
    except Exception as e:
        print(f"[diagnose_nl] Agentic error: {e}")
        agentic = {
            "analysisStatus": "error",
            "rootCauses": [],
            "affectedComponents": [],
            "correctiveActions": [],
            "fixHistory": [],
            "finalConverged": False,
            "toolCalls": [],
            "initialDiagnosis": {},
            "agentActions": [],
            "finalState": {},
            "beforeState": {},
            "afterState": {},
        }

    return {
        "generationStatus": "success",
        "generationError": None,
        "generatedCode": gen_result["generated_code"],
        "generatedGroundTruth": {
            "failureType": ground_truth.failure_type,
            "rootCauses": ground_truth.root_causes,
            "affectedComponents": ground_truth.affected_components,
            "knownFix": ground_truth.known_fix,
        },
        "baseline": baseline,
        "agentic": agentic,
        "responseType": response_type,
        "textAnswer": text_answer,
    }



# ---------------------
#  Entrypoint
# ---------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
