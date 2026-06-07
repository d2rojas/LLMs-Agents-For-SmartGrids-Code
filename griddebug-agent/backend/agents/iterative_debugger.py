"""
Level 3: Iterative Debugger Agent

Extends the agentic pipeline with a propose-fix-verify loop.
The agent proposes a corrective action, applies it, re-runs power
flow, and evaluates whether the fix resolved the issue.
"""
from __future__ import annotations

import copy
import json
import time
from typing import Any

import pandapower as pp

MAX_FIX_ITERATIONS = 10
from rule_engine.preprocessor import Preprocessor
from tools.query_tools import QueryTools
from tools.simulation_tools import SimulationTools
from tools.modification_tools import ModificationTools
from tools.diagnostic_tools import DiagnosticTools


SYSTEM_PROMPT = """\
You are GridDebugAgent (Level 3: Iterative Debugger), an expert power systems \
engineer. You diagnose failed power flow simulations AND iteratively fix them.

You have access to both analysis and modification tools:

ANALYSIS TOOLS:
{analysis_tools}

MODIFICATION TOOLS:
{modification_tools}

Your workflow:
1. DIAGNOSE: Analyze evidence and identify root causes. If the user query specifies an initiating event (e.g. line disconnection), that is the primary root cause. Treat voltage/thermal violations as symptoms.
2. PROPOSE: Choose a minimal corrective action
3. APPLY: Call a modification tool to apply the fix
4. VERIFY: Re-run power flow to check if the fix worked
5. CHECK CONSTRAINTS: If it converges, YOU MUST run `check_overloads` and `check_voltage_violations`. A converged network with violations is NOT fixed!
6. ITERATE: If not fixed, try the next most likely correction

IMPORTANT: Before EVERY tool call, you MUST write a brief explanation of what \
you are about to do and why. Never call tools silently.

After each fix attempt, report:
- What you tried and why
- Whether it improved the situation (including remaining violations)
- What to try next (if needed)

When the simulation converges with all constraints satisfied, OR you've \
exhausted reasonable fixes, output your final report prefixed with \
"FINAL REPORT:" including a summary of all attempted fixes.
"""

USER_PROMPT_TEMPLATE = """\
== NETWORK: {network_name} ==
== FAILURE CATEGORY: {failure_category} ==

{user_query_section}== PREPROCESSED EVIDENCE ==
{evidence_text}

== TRIGGERED RULES ==
{rules_text}

{task_instruction}
"""


class IterativeDebuggerAgent:
    """
    Level 3 agent: diagnose + iterative fix-verify loop.
    Extends agentic pipeline with modification tool access.
    """

    def __init__(self, llm_client, max_iterations: int = MAX_FIX_ITERATIONS):
        self.llm_client = llm_client
        self.preprocessor = Preprocessor()
        self.max_iterations = max_iterations

    def diagnose(self, net: pp.pandapowerNet, network_name: str = "unknown", user_query: str = "") -> dict[str, Any]:
        """
        Run iterative diagnosis + fix loop.

        Args:
            user_query: Optional user question. When provided for direct_answer
                        queries, the agent uses query tools to answer instead of
                        running the full fix loop.

        Returns:
            dict with keys: "level", "response", "fix_history",
            "final_converged", "iterations_used"
        """
        # Save original for comparison
        original_net = copy.deepcopy(net)

        # Preprocess
        context = self.preprocessor.process(net)

        # Build prompt
        rules_text = self._format_rules(context["triggered_rules"])
        if user_query:
            user_query_section = f"== USER QUERY ==\n{user_query}\n\n"
            task_instruction = (
                "Please answer the user query above using the available tools. "
                "Call the appropriate tools to retrieve the requested information, "
                "then provide a clear, concise answer.\n\n"
                "CRITICAL: Do NOT apply corrective fixes (load shedding, shunt compensation, "
                "voltage setpoint changes, etc.) unless the user explicitly asks you to fix or "
                "correct something. If the user asks to 'summarize violations' or 'evaluate impact', "
                "just REPORT the findings. You may use modification tools ONLY if the query requires "
                "setting up a scenario (e.g. 'take line X out of service', 'double all loads').\n\n"
                "IMPORTANT RULES:\n"
                "- Be concise. Use short bullet points, not paragraphs. No filler or pleasantries.\n"
                "- For 'total active power loss', compute the sum of pl_mw across ALL lines "
                "(or use total_gen_p_mw - total_load_p_mw from get_power_balance). Do NOT report a single line's loss.\n"
                "- Report exact numeric values with units. Do not round excessively.\n"
                "- Do not add conversational text like 'feel free to ask' or 'if you need further analysis'."
            )
        else:
            user_query_section = ""
            task_instruction = (
                "Please diagnose the issue and iteratively apply fixes until the power flow "
                "converges without violations, or until you've exhausted reasonable corrections."
            )
        user_prompt = USER_PROMPT_TEMPLATE.format(
            network_name=network_name,
            failure_category=context["failure_category"],
            evidence_text=context["evidence_text"],
            rules_text=rules_text,
            user_query_section=user_query_section,
            task_instruction=task_instruction,
        )

        # Generate initial diagnosis from preprocessor context
        initial_diagnosis = self._generate_initial_diagnosis(context)

        # Run iterative loop
        fix_history = []
        conversation = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        final_response = self._llm_fix_loop(
            net, conversation, fix_history
        )

        # Capture final state after all fixes
        final_state = self._capture_final_state(net)

        # Generate concise query summary if user asked a question
        query_summary = None
        if user_query:
            query_summary = self._generate_query_summary(user_query, fix_history, final_response)

        return {
            "level": "iterative_debugger",
            "response": final_response,
            "query_summary": query_summary,
            # New structured fields
            "initial_diagnosis": initial_diagnosis,
            "agent_actions": fix_history,  # Unified list with reasoning + phase
            "final_state": final_state,
            # Backward compatible fields
            "fix_history": fix_history,
            "final_converged": final_state["converged"],
            "iterations_used": len(fix_history),
            "evidence": context["evidence"],
            "failure_category": context["failure_category"],
        }

    # ── Observation-driven helpers ──────────────────────────────────

    @staticmethod
    def _observe(net: pp.pandapowerNet) -> dict:
        """Run power flow + all diagnostics to snapshot full network health."""
        try:
            pp.runpp(net)
            converged = bool(net.converged)
        except Exception:
            converged = False

        disconnected_info = DiagnosticTools.find_disconnected_areas(net)
        disconnected_buses = set(disconnected_info.get("disconnected_buses", []))

        # Identify disconnected buses that still have active loads
        # (these need fixing).  Inert disconnected buses (no active load)
        # are physically isolated but harmless — NaN voltage is expected.
        disc_with_load: set[int] = set()
        for idx, row in net.load.iterrows():
            if row.get("in_service", True) and int(row["bus"]) in disconnected_buses:
                if row.get("p_mw", 0) > 0 or row.get("q_mvar", 0) > 0:
                    disc_with_load.add(int(row["bus"]))
        inert_buses = disconnected_buses - disc_with_load

        # NaN voltages on inert disconnected buses are expected; only flag
        # NaN on connected (or load-bearing disconnected) buses.
        has_nan_voltage = False
        if converged and hasattr(net, "res_bus") and not net.res_bus.empty:
            nan_buses = set(net.res_bus[net.res_bus["vm_pu"].isna()].index.astype(int))
            real_nan = nan_buses - inert_buses
            has_nan_voltage = len(real_nan) > 0

        violations = DiagnosticTools.check_voltage_violations(net) if converged else {}
        overloads = DiagnosticTools.check_overloads(net) if converged else {}

        # Filter out voltage violations on inert disconnected buses
        if violations and inert_buses:
            violations = dict(violations)  # copy
            for key in ("undervoltage_buses", "overvoltage_buses"):
                if key in violations:
                    violations[key] = [
                        v for v in violations[key] if v["bus"] not in inert_buses
                    ]
            violations["total_violations"] = (
                len(violations.get("undervoltage_buses", []))
                + len(violations.get("overvoltage_buses", []))
            )

        return {
            "converged": converged,
            "has_nan_voltage": has_nan_voltage,
            "disconnected_buses": sorted(disc_with_load),  # only actionable ones
            "inert_buses": sorted(inert_buses),
            "violations": violations,
            "overloads": overloads,
        }

    @staticmethod
    def _is_healthy(state: dict) -> bool:
        """True only when converged, no real NaN voltages, and zero violations."""
        if not state["converged"] or state["has_nan_voltage"]:
            return False
        if state["violations"].get("total_violations", 0) > 0:
            return False
        if len(state["overloads"].get("overloaded_lines", [])) > 0:
            return False
        if len(state["overloads"].get("overloaded_trafos", [])) > 0:
            return False
        return True

    def _llm_fix_loop(
        self,
        net: pp.pandapowerNet,
        conversation: list[dict],
        fix_history: list[dict],
    ) -> str:
        """LLM-driven fix loop with function calling."""
        for i in range(self.max_iterations * 3):  # More iterations for LLM
            try:
                tools = self._get_openai_tools()
                completion = self.llm_client.chat.completions.create(
                    model="gpt-4o",
                    messages=conversation,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=2000,
                )

                message = completion.choices[0].message

                if message.tool_calls:
                    # Capture LLM reasoning (the text content before tool calls)
                    reasoning_text = message.content or ""
                    conversation.append(message.model_dump())

                    for tool_call in message.tool_calls:
                        fn_name = tool_call.function.name
                        fn_args = json.loads(tool_call.function.arguments)
                        phase = self._classify_tool_phase(fn_name)

                        result = self._execute_tool(net, fn_name, fn_args)
                        fix_history.append({
                            "iteration": i,
                            "tool": fn_name,
                            "args": fn_args,
                            "result": result,
                            "reasoning": reasoning_text,
                            "phase": phase,
                        })

                        conversation.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result),
                        })
                else:
                    return message.content or ""

            except Exception as e:
                if "429" in str(e):
                    time.sleep(5)
                    continue
                return f"Iterative debugger error at step {i}: {str(e)}"

        return "Max iterations reached in iterative debugger."

    def _execute_tool(self, net: pp.pandapowerNet, name: str, args: dict) -> Any:
        """Dispatch tool calls — includes both analysis and modification tools."""
        tool_map = {
            # Analysis tools
            "get_network_summary": lambda: QueryTools.get_network_summary(net),
            "get_bus_data": lambda: QueryTools.get_bus_data(net, **args),
            "get_line_data": lambda: QueryTools.get_line_data(net, **args),
            "get_gen_data": lambda: QueryTools.get_gen_data(net, **args),
            "get_voltage_profile": lambda: QueryTools.get_voltage_profile(net),
            "get_loading_profile": lambda: QueryTools.get_loading_profile(net),
            "get_power_balance": lambda: QueryTools.get_power_balance(net),
            "get_line_results": lambda: QueryTools.get_line_results(net, **args),
            "get_bus_results": lambda: QueryTools.get_bus_results(net, **args),
            "run_power_flow": lambda: SimulationTools.run_power_flow(net),
            "run_dc_power_flow": lambda: SimulationTools.run_dc_power_flow(net),
            "run_n1_contingency": lambda: SimulationTools.run_n1_contingency(net, **args),
            "run_short_circuit": lambda: SimulationTools.run_short_circuit(net, **args),
            "run_opf": lambda: SimulationTools.run_opf(net, **args),
            "save_network_snapshot": lambda: SimulationTools.save_network_snapshot(net, **args),
            "restore_network_snapshot": lambda: SimulationTools.restore_network_snapshot(net, **args),
            "run_full_diagnostics": lambda: DiagnosticTools.run_full_diagnostics(net),
            "check_overloads": lambda: DiagnosticTools.check_overloads(net, **args),
            "check_voltage_violations": lambda: DiagnosticTools.check_voltage_violations(net, **args),
            "find_disconnected_areas": lambda: DiagnosticTools.find_disconnected_areas(net),
            # Modification tools
            "shed_load": lambda: ModificationTools.shed_load(net, **args),
            "curtail_load": lambda: ModificationTools.curtail_load(net, **args),
            "adjust_generation": lambda: ModificationTools.adjust_generation(net, **args),
            "add_reactive_compensation": lambda: ModificationTools.add_reactive_compensation(net, **args),
            "add_shunt_compensation": lambda: ModificationTools.add_shunt_compensation(net, **args),
            "toggle_element": lambda: ModificationTools.toggle_element(net, **args),
            "switch_element": lambda: ModificationTools.switch_element(net, **args),
            "adjust_voltage_setpoint": lambda: ModificationTools.adjust_voltage_setpoint(net, **args),
            "scale_all_loads": lambda: ModificationTools.scale_all_loads(net, **args),
        }

        if name in tool_map:
            try:
                return tool_map[name]()
            except Exception as e:
                return {"error": str(e)}
        return {"error": f"Unknown tool: {name}"}

    def _build_system_prompt(self) -> str:
        all_analysis = (
            QueryTools.TOOL_DEFINITIONS +
            SimulationTools.TOOL_DEFINITIONS +
            DiagnosticTools.TOOL_DEFINITIONS
        )
        all_mods = ModificationTools.TOOL_DEFINITIONS

        analysis_desc = "\n".join(f"  - {t['name']}: {t['description']}" for t in all_analysis)
        mod_desc = "\n".join(f"  - {t['name']}: {t['description']}" for t in all_mods)

        return SYSTEM_PROMPT.format(
            analysis_tools=analysis_desc,
            modification_tools=mod_desc,
        )

    def _get_openai_tools(self) -> list[dict]:
        all_tools = (
            QueryTools.TOOL_DEFINITIONS +
            SimulationTools.TOOL_DEFINITIONS +
            DiagnosticTools.TOOL_DEFINITIONS +
            ModificationTools.TOOL_DEFINITIONS
        )
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": {
                        "type": "object",
                        "properties": t.get("parameters", {}),
                        "required": [],
                    },
                },
            }
            for t in all_tools
        ]

    def _format_rules(self, rules: list[dict]) -> str:
        if not rules:
            return "No rules triggered."
        lines = []
        for r in rules:
            lines.append(f"[{r['severity'].upper()}] {r['rule_name']}: {r['description']}")
            for action in r.get("suggested_actions", []):
                lines.append(f"  → {action}")
        return "\n".join(lines)

    @staticmethod
    def _classify_tool_phase(tool_name: str) -> str:
        """Classify a tool call as diagnostic, fix, or verify."""
        diagnostic_tools = {
            "get_network_summary", "get_bus_data", "get_line_data", "get_gen_data",
            "get_voltage_profile", "get_loading_profile", "get_power_balance",
            "get_line_results", "get_bus_results",
            "check_overloads", "check_voltage_violations", "find_disconnected_areas",
            "run_n1_contingency", "run_short_circuit", "run_opf",
        }
        fix_tools = {
            "shed_load", "curtail_load", "adjust_generation", "add_shunt_compensation",
            "add_reactive_compensation", "toggle_element", "switch_element",
            "adjust_voltage_setpoint", "scale_all_loads",
            "save_network_snapshot", "restore_network_snapshot",
        }
        verify_tools = {"run_power_flow", "run_dc_power_flow", "run_full_diagnostics"}

        if tool_name in diagnostic_tools:
            return "diagnostic"
        elif tool_name in fix_tools:
            return "fix"
        elif tool_name in verify_tools:
            return "verify"
        return "diagnostic"

    def _generate_initial_diagnosis(self, context: dict) -> dict:
        """Extract initial diagnosis from preprocessor context before fixes."""
        triggered_rules = context.get("triggered_rules", [])
        evidence = context.get("evidence", {})

        # Extract root causes from triggered rules (critical/high severity)
        root_causes = []
        for rule in triggered_rules:
            severity = rule.get("severity", "").lower()
            if severity in ("critical", "high"):
                root_causes.append(f"{rule['rule_name']}: {rule['description']}")

        # Extract affected components from evidence (correct nested paths)
        affected_components = []

        # Voltage violations (nested under "voltages")
        voltages = evidence.get("voltages", {})
        for v in voltages.get("undervoltage_buses", []):
            bus_idx = v.get("index", v.get("bus", "?"))
            vm_pu = v.get("vm_pu", 0)
            affected_components.append(f"Bus {bus_idx} (undervoltage: {vm_pu:.3f} pu)")
        for v in voltages.get("overvoltage_buses", []):
            bus_idx = v.get("index", v.get("bus", "?"))
            vm_pu = v.get("vm_pu", 0)
            affected_components.append(f"Bus {bus_idx} (overvoltage: {vm_pu:.3f} pu)")

        # Line overloads (nested under "line_loading")
        line_loading = evidence.get("line_loading", {})
        for line in line_loading.get("overloaded_lines", []):
            line_idx = line.get("index", line.get("line_index", "?"))
            from_bus = line.get("from_bus", "?")
            to_bus = line.get("to_bus", "?")
            loading = line.get("loading_pct", line.get("loading_percent", 0))
            affected_components.append(
                f"Line {line_idx} ({from_bus}-{to_bus}) overloaded at {loading:.1f}%"
            )

        # Transformer overloads (nested under "trafo_loading")
        trafo_loading = evidence.get("trafo_loading", {})
        for trafo in trafo_loading.get("overloaded_trafos", []):
            trafo_idx = trafo.get("index", trafo.get("trafo_index", "?"))
            loading = trafo.get("loading_pct", trafo.get("loading_percent", 0))
            affected_components.append(
                f"Transformer {trafo_idx} overloaded at {loading:.1f}%"
            )

        # Disconnected buses (nested under "topology")
        topology = evidence.get("topology", {})
        disc_buses = topology.get("disconnected_buses", [])
        if disc_buses:
            affected_components.append(f"Disconnected buses: {disc_buses}")

        # Convergence status (nested under "convergence")
        convergence = evidence.get("convergence", {})
        converged_initially = convergence.get("converged", False)

        return {
            "root_causes": root_causes,
            "affected_components": affected_components,
            "failure_category": context.get("failure_category", "unknown"),
            "converged_initially": converged_initially,
        }

    def _capture_final_state(self, net: pp.pandapowerNet) -> dict:
        """Capture the final state after all fixes."""
        state = self._observe(net)

        remaining_violations = []

        # Voltage violations
        violations = state.get("violations", {})
        for v in violations.get("undervoltage_buses", []):
            remaining_violations.append(f"Bus {v['bus']} undervoltage: {v['vm_pu']:.3f} pu")
        for v in violations.get("overvoltage_buses", []):
            remaining_violations.append(f"Bus {v['bus']} overvoltage: {v['vm_pu']:.3f} pu")

        # Thermal overloads
        overloads = state.get("overloads", {})
        for line in overloads.get("overloaded_lines", []):
            remaining_violations.append(
                f"Line {line['line_index']} overloaded at {line['loading_percent']:.1f}%"
            )
        for trafo in overloads.get("overloaded_trafos", []):
            remaining_violations.append(
                f"Transformer {trafo['trafo_index']} overloaded at {trafo['loading_percent']:.1f}%"
            )

        return {
            "converged": state["converged"],
            "remaining_violations": remaining_violations,
            "is_healthy": self._is_healthy(state),
        }

    def _generate_query_summary(self, user_query: str, fix_history: list[dict], full_response: str) -> str | None:
        """Generate a concise summary answering just the user's query, separate from fix details."""
        # Collect tool results (diagnostic tools only) for context
        diagnostic_results = []
        for action in fix_history:
            if action.get("phase") == "diagnostic":
                diagnostic_results.append({
                    "tool": action["tool"],
                    "result": action["result"],
                })

        try:
            completion = self.llm_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": (
                        "You are a power systems engineer. Given a user query, tool results, and the agent's "
                        "full response, produce a summary that answers the original query. "
                        "You MUST include every piece of information the user explicitly asked for. "
                        "Do NOT omit any requested quantity. Do NOT mention any corrective actions or fixes attempted. "
                        "Use short bullet points with exact numeric values and units. "
                        "No filler, no pleasantries."
                    )},
                    {"role": "user", "content": (
                        f"USER QUERY: {user_query}\n\n"
                        f"DIAGNOSTIC TOOL RESULTS:\n{json.dumps(diagnostic_results, indent=2)[:3000]}\n\n"
                        f"AGENT FULL RESPONSE:\n{full_response[:2000]}\n\n"
                        "Answer the user's query. Include ALL requested information — do not drop any."
                    )},
                ],
                temperature=0.2,
                max_tokens=500,
            )
            return completion.choices[0].message.content or None
        except Exception:
            return None
