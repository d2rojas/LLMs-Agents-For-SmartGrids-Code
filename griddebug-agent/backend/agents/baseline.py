"""
Level 1: Baseline LLM Agent

Passes raw solver outputs directly to an LLM for natural language
explanation. No tool access — establishes what an LLM can infer
from unstructured data alone.

Uses OpenAI function calling for reliable structured output.
"""
from __future__ import annotations

import json
from typing import Any

import pandapower as pp

from rule_engine.evidence_collector import EvidenceCollector


# Function schema for structured diagnosis output
DIAGNOSIS_FUNCTION = {
    "type": "function",
    "function": {
        "name": "report_diagnosis",
        "description": "Report the diagnosis results with affected components",
        "parameters": {
            "type": "object",
            "properties": {
                "root_causes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of root causes, ranked from most to least likely"
                },
                "affected_components": {
                    "type": "object",
                    "properties": {
                        "bus": {"type": "array", "items": {"type": "integer"}, "description": "Bus indices with violations"},
                        "line": {"type": "array", "items": {"type": "integer"}, "description": "Line indices with violations"},
                        "load": {"type": "array", "items": {"type": "integer"}, "description": "Load indices causing issues"},
                        "gen": {"type": "array", "items": {"type": "integer"}, "description": "Generator indices causing issues"},
                        "trafo": {"type": "array", "items": {"type": "integer"}, "description": "Transformer indices with violations"},
                        "ext_grid": {"type": "array", "items": {"type": "integer"}, "description": "External grid indices"}
                    },
                    "required": ["bus", "line", "load", "gen", "trafo", "ext_grid"]
                },
                "corrective_actions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific corrective actions to fix the issues"
                },
                "confidence": {
                    "type": "string",
                    "description": "Confidence level assessment"
                }
            },
            "required": ["root_causes", "affected_components", "corrective_actions", "confidence"]
        }
    }
}

SYSTEM_PROMPT = """\
You are GridDebugAgent, an expert power systems engineer \
specializing in diagnosing failed power flow simulations run with pandapower.

## Your Analysis Approach

When the power flow DID NOT CONVERGE:
1. First check the LOAD vs GENERATION comparison — is total load far exceeding \
generation capacity? If load/gen ratio >> 1.0, the primary root cause is EXCESSIVE LOAD \
or INSUFFICIENT GENERATION, not impedance or topology issues.
2. Check for disconnected buses or isolated elements that might prevent power delivery.
3. The pandapower diagnostics section may contain generic warnings (impedance, bus indexing) \
that are present on MANY healthy networks. Do NOT cite these as root causes unless they \
directly contribute to non-convergence.

When the power flow CONVERGED but has violations:
1. Check bus voltages for under/over-voltage violations.
2. Check line/trafo loading for thermal overloads (>100%).
3. Trace the violation to its root cause (e.g., heavy loading → voltage drop).

## Output Instructions

You MUST call the report_diagnosis function with your findings.

In affected_components, list the SPECIFIC indices of components with violations or that \
directly caused the failure. Use the exact indices from the evidence data.

Also write a prose explanation in your message describing the diagnosis in detail."""

USER_PROMPT_TEMPLATE = """\
The following power flow simulation has {status}.

Network: {network_name}
Buses: {bus_count} | Lines: {line_count} | Generators: {gen_count} | Loads: {load_count}

{user_query_str}

{evidence_text}

Analyze this evidence and call the report_diagnosis function with your findings. \
Be specific — cite component indices from the evidence (e.g., Bus 5, Line 3, Gen 2)."""


class BaselineAgent:
    """
    Level 1 agent: raw solver output → LLM explanation.
    No tool access, no rule engine — pure LLM interpretation.
    Uses function calling for structured output.
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.collector = EvidenceCollector()

    def diagnose(self, net: pp.pandapowerNet, network_name: str = "unknown", user_query: str = "") -> dict[str, Any]:
        """
        Run baseline diagnosis on a network.

        Args:
            net: pandapower network (after failed or converged PF attempt)
            network_name: name of the test network
            user_query: optional user query

        Returns:
            dict with keys: "prompt", "response", "evidence", "structured_output"
        """
        # Collect evidence
        report = self.collector.collect(net)

        # Build prompt
        status = "FAILED TO CONVERGE" if not report.converged else "CONVERGED"
        user_query_str = f"== USER QUERY ==\n{user_query}\n" if user_query else ""
        prompt = USER_PROMPT_TEMPLATE.format(
            status=status,
            network_name=network_name,
            bus_count=report.bus_count,
            line_count=report.line_count,
            gen_count=report.gen_count,
            load_count=len(net.load),
            user_query_str=user_query_str,
            evidence_text=report.to_text(),
        )

        # Call LLM with function calling
        response, structured = self._call_llm(prompt)

        return {
            "level": "baseline",
            "prompt": prompt,
            "response": response,
            "evidence": report.to_dict(),
            "structured_output": structured,
        }

    def _call_llm(self, user_prompt: str) -> tuple[str, dict | None]:
        """
        Call the LLM with function calling for structured output.

        Returns:
            tuple of (prose_response, structured_data)
        """
        try:
            completion = self.llm_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                tools=[DIAGNOSIS_FUNCTION],
                tool_choice={"type": "function", "function": {"name": "report_diagnosis"}},
                temperature=0.3,
                max_tokens=2000,
            )

            message = completion.choices[0].message
            prose = message.content or ""

            # Extract structured data from function call
            structured = None
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "report_diagnosis":
                        try:
                            structured = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            pass
                        break

            # Build prose response from structured data if no prose
            if not prose and structured:
                prose = self._build_prose_from_structured(structured)

            return prose, structured

        except Exception as e:
            return f"LLM call failed: {str(e)}", None

    def _build_prose_from_structured(self, structured: dict) -> str:
        """Build a prose report from structured data."""
        lines = []

        lines.append("## Root Causes")
        for cause in structured.get("root_causes", []):
            lines.append(f"- {cause}")
        lines.append("")

        lines.append("## Affected Components")
        affected = structured.get("affected_components", {})
        component_names = {"bus": "Buses", "line": "Lines", "load": "Loads",
                          "gen": "Generators", "trafo": "Transformers", "ext_grid": "External Grids"}
        for comp_type, display_name in component_names.items():
            indices = affected.get(comp_type, [])
            if indices:
                lines.append(f"- {display_name}: {', '.join(map(str, indices))}")
        lines.append("")

        lines.append("## Corrective Actions")
        for action in structured.get("corrective_actions", []):
            lines.append(f"- {action}")
        lines.append("")

        lines.append("## Confidence Assessment")
        lines.append(f"- {structured.get('confidence', 'Unknown')}")

        return "\n".join(lines)

