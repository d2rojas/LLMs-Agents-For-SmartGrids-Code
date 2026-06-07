"""
Level 2: Agentic Pipeline Agent

ReAct-style agent that receives rule-engine context and can call
query/simulation/diagnostic tools to gather additional evidence.
Produces a structured DiagnosticReport.
"""
from __future__ import annotations

import copy
import json
import time
from typing import Any

import pandapower as pp

from rule_engine.preprocessor import Preprocessor
from tools.query_tools import QueryTools
from tools.simulation_tools import SimulationTools
from tools.diagnostic_tools import DiagnosticTools
from tools.grid_actions import GridActions


# ── Prompt templates ───────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are GridDebugAgent Level 2, an expert power systems engineer with tool \
access for deep diagnosis of power flow simulation issues.

You have been provided with preprocessed evidence from a pandapower simulation, \
including rule-engine classifications that have already identified likely failure modes.

## Analysis & Iterative Debugging Strategy

1. FIRST read the user query (if provided) and the triggered rules carefully. If the user query describes a specific contingency or network mutation (e.g., disconnecting a line), consider that action as the primary root cause. The triggered rules pre-classify the resulting symptoms (e.g., undervoltage, thermal overloads).
2. For NON-CONVERGENCE: Focus on the load-vs-generation balance. If loads far \
exceed generation, the root cause is load/generation imbalance, NOT impedance or \
bus indexing issues. Use tools to verify the load/gen data.
3. For VOLTAGE VIOLATIONS: Use get_voltage_profile to identify specific buses, \
then trace back to root cause (overloaded feeder, missing reactive support).
4. For THERMAL OVERLOADS: Use get_loading_profile to rank overloaded elements, \
then check contingency impacts.
5. ITERATIVE DEBUGGING: If you identify a root cause, you MUST try to fix it using the Grid Action tools \
(e.g., curtail_load, adjust_generation, switch_line). After taking an action, you MUST call run_power_flow \
to verify if the network converges and if violations are resolved. \
Repeat this propose->act->verify loop until the network is secure (0 violations) or you reach a dead end.
6. Use tools STRATEGICALLY — plan your actions and observe the results.

## Available Tools
{tool_descriptions}

## Output Requirements

If a specific USER QUERY is provided, your primary goal is to answer that query directly using your tools. You MUST output ONLY the direct answer exactly as requested (e.g., a simple bulleted list of violations). Do NOT use the standard Root Causes formatting, do NOT write "FINAL REPORT:", and do NOT include conversational filler like "I will identify...". Just output the exact requested information.

If the user asks to summarize contingency limit violations, you MUST use exactly this concise one-line format for each tested outage:
- Line <ID> outage: <N> voltage violation (bus <ID> at <V> pu < <LIMIT> pu); <M> branch overloads.
or
- Line <ID> outage: no operational limit violations.
Make sure to apply this format strictly and do not add any conversational text.

If no user query is provided, or the query asks for a general diagnosis without specific formatting requirements, output "FINAL REPORT:" followed by:
## Root Causes (Identify the initiating event, e.g., line disconnection, as the primary root cause. Do NOT list symptoms like "Undervoltage" as the root cause if an initiating event is known.)
## Affected Components (List the components experiencing symptoms or involved in the failure, e.g. "Bus 117: Under-voltage")
## Corrective Actions (minimal, engineering-feasible, specific)
## Reasoning Trace (summarize analysis steps and tool findings)
"""

USER_PROMPT_TEMPLATE = """\
== NETWORK: {network_name} ==
== FAILURE CATEGORY: {failure_category} ==
{user_query_str}

{evidence_text}

== TRIGGERED RULES (from rule engine) ==
{rules_text}

== NETWORK SUMMARY ==
{network_summary}

Analyze this case using the triggered rules as your starting hypothesis. \
Use tools to gather evidence if needed, then produce your FINAL REPORT."""


class AgenticPipelineAgent:
    """
    Level 2 agent: rule-engine preprocessed context + tool access.
    Uses a ReAct loop to iteratively gather evidence.
    """

    MAX_TOOL_CALLS = 10

    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.preprocessor = Preprocessor()

    def diagnose(self, net: pp.pandapowerNet, network_name: str = "unknown", user_query: str = "") -> dict[str, Any]:
        """
        Run agentic diagnosis with tool access.

        Returns:
            dict with keys: "level", "prompt", "response", "evidence",
            "tool_calls", "conversation"
        """
        # Step 1: Preprocess
        context = self.preprocessor.process(net)

        # Step 2: Build initial prompt
        rules_text = self._format_rules(context["triggered_rules"])
        network_summary = json.dumps(context["network_summary"], indent=2)

        user_query_str = f"== USER QUERY ==\n{user_query}\n" if user_query else ""
        user_prompt = USER_PROMPT_TEMPLATE.format(
            network_name=network_name,
            failure_category=context["failure_category"],
            user_query_str=user_query_str,
            evidence_text=context["evidence_text"],
            rules_text=rules_text,
            network_summary=network_summary,
        )

        # Step 3: Run ReAct loop
        tool_calls_log = []
        conversation = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        final_response = self._run_react_loop(net, conversation, tool_calls_log)

        return {
            "level": "agentic_pipeline",
            "prompt": user_prompt,
            "response": final_response,
            "evidence": context["evidence"],
            "triggered_rules": context["triggered_rules"],
            "failure_category": context["failure_category"],
            "tool_calls": tool_calls_log,
            "conversation": conversation,
        }

    def _build_system_prompt(self) -> str:
        """Build system prompt with tool descriptions."""
        all_tools = (
            QueryTools.TOOL_DEFINITIONS +
            SimulationTools.TOOL_DEFINITIONS +
            DiagnosticTools.TOOL_DEFINITIONS +
            GridActions.TOOL_DEFINITIONS
        )
        tool_desc = "\n".join(
            f"- {t['name']}: {t['description']}" for t in all_tools
        )
        return SYSTEM_PROMPT.format(tool_descriptions=tool_desc)

    def _run_react_loop(
        self,
        net: pp.pandapowerNet,
        conversation: list[dict],
        tool_calls_log: list[dict],
    ) -> str:
        """
        Run the ReAct loop: call LLM, parse tool calls, execute tools,
        feed results back. Repeat until final report or max iterations.
        """
        for i in range(self.MAX_TOOL_CALLS):
            try:
                # Get tool schemas for function calling
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

                # Check if the model wants to call a tool
                if message.tool_calls:
                    conversation.append(message.model_dump())

                    for tool_call in message.tool_calls:
                        fn_name = tool_call.function.name
                        fn_args = json.loads(tool_call.function.arguments)

                        # Execute the tool
                        result = self._execute_tool(net, fn_name, fn_args)
                        tool_calls_log.append({
                            "iteration": i,
                            "tool": fn_name,
                            "args": fn_args,
                            "result": result,
                        })

                        conversation.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result),
                        })
                else:
                    # Model produced a final response
                    return message.content or ""

            except Exception as e:
                if "429" in str(e):
                    time.sleep(5)
                    continue
                return f"Agent loop error at iteration {i}: {str(e)}"

        return "Max tool call iterations reached. Please review the gathered evidence."

    def _execute_tool(self, net: pp.pandapowerNet, name: str, args: dict) -> Any:
        """Dispatch a tool call to the appropriate function."""
        tool_map = {
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
            "adjust_generation": lambda: GridActions.adjust_generation(net, **args),
            "curtail_load": lambda: GridActions.curtail_load(net, **args),
            "switch_line": lambda: GridActions.switch_line(net, **args),
            "switch_shunt": lambda: GridActions.switch_shunt(net, **args),
        }

        if name in tool_map:
            try:
                return tool_map[name]()
            except Exception as e:
                return {"error": str(e)}
        return {"error": f"Unknown tool: {name}"}

    def _get_openai_tools(self) -> list[dict]:
        """Build OpenAI function-calling tool schemas."""
        all_tools = (
            QueryTools.TOOL_DEFINITIONS +
            SimulationTools.TOOL_DEFINITIONS +
            DiagnosticTools.TOOL_DEFINITIONS +
            GridActions.TOOL_DEFINITIONS
        )
        openai_tools = []
        for t in all_tools:
            schema = {
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
            openai_tools.append(schema)
        return openai_tools

    def _format_rules(self, rules: list[dict]) -> str:
        """Format triggered rules for prompt."""
        if not rules:
            return "No rules triggered."
        lines = []
        for r in rules:
            lines.append(f"[{r['severity'].upper()}] {r['rule_name']}: {r['description']}")
            for action in r.get("suggested_actions", []):
                lines.append(f"  → {action}")
        return "\n".join(lines)

