"""
Natural Language Scenario Generator.

Translates user natural language failure descriptions into executable
pandapower network mutations using an LLM, then executes them safely.
"""
from __future__ import annotations

import copy
import json
import re
from typing import Any

import pandapower as pp
import pandapower.networks as pn

from .base_scenarios import ScenarioResult, load_network
from .code_sandbox import execute_safely


# ── Few-shot examples ──────────────────────────────────────────────

FEW_SHOT_EXAMPLES = [
    {
        "description": "Scale all loads by 20x to cause extreme power mismatch and non-convergence",
        "network": "case14",
        "response": {
            "response_type": "full_diagnosis",
            "text_answer": "I will scale all loads by 20x to simulate extreme power mismatch and non-convergence.",
            "mutation_code": "net.load['p_mw'] *= 20.0\nnet.load['q_mvar'] *= 20.0",
            "ground_truth": {
                "failure_type": "nonconvergence",
                "root_causes": [
                    "All loads scaled by 20x",
                    "Total active power demand far exceeds available generation",
                    "Newton-Raphson solver cannot find a feasible operating point"
                ],
                "affected_components": {"load": "all"},
                "known_fix": "Reduce loads to original values or add generation capacity"
            }
        }
    },
    {
        "description": "Take all generators out of service",
        "network": "case14",
        "response": {
            "mutation_code": "net.gen['in_service'] = False\nif len(net.sgen) > 0:\n    net.sgen['in_service'] = False",
            "ground_truth": {
                "failure_type": "nonconvergence",
                "root_causes": [
                    "All generators taken out of service",
                    "Ext_grid alone cannot satisfy total demand",
                    "Severe voltage collapse across the network"
                ],
                "affected_components": {"gen": "all", "sgen": "all"},
                "known_fix": "Restore generators to service or reduce total demand"
            }
        }
    },
    {
        "description": "Add a large 100MW load at the bus with the fewest connections to cause thermal overload",
        "network": "case14",
        "response": {
            "mutation_code": (
                "slack_bus = int(net.ext_grid['bus'].iloc[0])\n"
                "bus_connections = {}\n"
                "for _, row in net.line.iterrows():\n"
                "    for b in [int(row['from_bus']), int(row['to_bus'])]:\n"
                "        bus_connections[b] = bus_connections.get(b, 0) + 1\n"
                "candidates = {b: c for b, c in bus_connections.items() if b != slack_bus}\n"
                "target_bus = min(candidates, key=candidates.get)\n"
                "pp.create_load(net, bus=target_bus, p_mw=100.0, q_mvar=30.0, name='concentrated_load')"
            ),
            "ground_truth": {
                "failure_type": "thermal",
                "root_causes": [
                    "Large load (100 MW) added at weakly connected bus",
                    "Power must flow through few connecting lines",
                    "Connected lines exceed thermal rating"
                ],
                "affected_components": {"bus": "target_bus", "line": "connected lines"},
                "known_fix": "Add parallel lines, add local generation, or redistribute load"
            }
        }
    },
    {
        "description": "Triple all loads to cause under-voltage at remote buses",
        "network": "case14",
        "response": {
            "mutation_code": "net.load['p_mw'] *= 3.0\nnet.load['q_mvar'] *= 3.0",
            "ground_truth": {
                "failure_type": "voltage",
                "root_causes": [
                    "All loads scaled by 3x",
                    "Increased reactive power demand causes voltage drop",
                    "Buses far from generation experience under-voltage"
                ],
                "affected_components": {"load": "all", "bus": "remote buses"},
                "known_fix": "Add reactive compensation (shunt capacitors) at affected buses"
            }
        }
    },
    {
        "description": "What is the voltage on bus 4 in the default case?",
        "network": "case14",
        "response": {
            "response_type": "direct_answer",
            "text_answer": "",
            "mutation_code": "",
            "ground_truth": {
                "failure_type": "normal",
                "root_causes": [],
                "affected_components": {},
                "known_fix": ""
            }
        }
    },
    {
        "description": "Show me a plot of the network without any failures",
        "network": "case14",
        "response": {
            "response_type": "plot_only",
            "text_answer": "Here is the interactive visualization of the baseline IEEE 14-bus network.",
            "mutation_code": "",
            "ground_truth": {
                "failure_type": "normal",
                "root_causes": [],
                "affected_components": {},
                "known_fix": ""
            }
        }
    },
]

# ── System prompt ──────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a pandapower expert that generates Python code to inject failures \
into IEEE test power networks.

Given a user's natural language description of a failure scenario, you must produce:
1. Python code that mutates a pandapower network object called `net` to create the failure.
2. A ground truth description of what the failure is.

## Available Variables
- `net`: a pandapower network (already loaded). You can access all standard \
pandapower DataFrames: `net.bus`, `net.line`, `net.load`, `net.gen`, \
`net.sgen`, `net.ext_grid`, `net.trafo`, `net.shunt`, etc.
- `pp`: the pandapower module (for creating elements, running power flow, etc.)
- `pd`: pandas
- `np`: numpy

## Network Index Ranges
{network_info}

## Rules
- Only mutate `net` — do NOT create a new network.
- Use standard pandapower API calls (e.g., `pp.create_load()`, direct DataFrame mutation).
- Do NOT import any modules — `pp`, `pd`, `np` are already available.
- Do NOT call `pp.runpp()` — the caller handles power flow execution.
- For short circuit analysis queries, classify as `direct_answer` so the agent can use its `run_short_circuit` tool. Do NOT generate short-circuit code directly.
- Keep code concise and focused on the mutation.

## Output Format
You MUST respond with valid JSON (no markdown fences) in this exact format. Set `response_type` to `text_only` ONLY for conceptual/theoretical questions that DO NOT require looking up specific data from the network. Set `response_type` to `plot_only` for simple plot requests. Set `response_type` to `direct_answer` for analytical queries OR when the user wants to retrieve specific information from the network (e.g. "What are the limits of bus 3?", "Which buses connect to line 11?") so the agentic pipeline can use tools to look it up. Set to `full_diagnosis` if the user wants to simulate a failure and diagnose it with full Root Causes / Affected Components formatting.
{{
  "response_type": "<text_only|plot_only|direct_answer|full_diagnosis>",
  "text_answer": "<Brief conceptual explanation. Leave empty or generic for direct_answer, as the agent will provide the real answer.>",
  "mutation_code": "<Python code as a single string with newlines. Leave empty if no mutation needed.>",
  "ground_truth": {{
    "failure_type": "<normal|nonconvergence|voltage|thermal|contingency>",
    "root_causes": ["cause 1", "cause 2"],
    "affected_components": {{"<element_type>": ["<indices or description>"]}},
    "known_fix": "<description of corrective action>"
  }}
}}
"""

USER_PROMPT_TEMPLATE = """\
Network: {network_name}
Description: {description}

Generate the mutation code and ground truth for this failure scenario."""


# ── Network info helper ────────────────────────────────────────────

def _get_network_info(network_name: str) -> str:
    """Get index ranges for the given network to include in the prompt."""
    net = load_network(network_name)
    lines = [
        f"Network: {network_name}",
        f"  Buses: {len(net.bus)} (indices 0–{len(net.bus)-1})",
        f"  Lines: {len(net.line)} (indices 0–{len(net.line)-1})",
        f"  Loads: {len(net.load)} (indices 0–{len(net.load)-1})",
        f"  Generators: {len(net.gen)} (indices 0–{len(net.gen)-1})" if len(net.gen) > 0 else "  Generators: 0",
        f"  Ext grids: {len(net.ext_grid)}",
        f"  Transformers: {len(net.trafo)}" if len(net.trafo) > 0 else "  Transformers: 0",
    ]
    return "\n".join(lines)


# ── Core class ─────────────────────────────────────────────────────

class NLScenarioGenerator:
    """
    LLM-powered generator that translates natural language failure
    descriptions into pandapower network mutations.
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def generate(
        self,
        description: str,
        network_name: str = "case14",
    ) -> dict[str, Any]:
        """
        Generate a failure scenario from a natural language description.

        Args:
            description: User's natural language failure description
            network_name: IEEE test network to use

        Returns:
            dict with keys:
                - "net": mutated pandapower network
                - "ground_truth": ScenarioResult
                - "generated_code": the mutation code string
                - "generation_status": "success" | "error"
                - "error": error message if any
        """
        # Step 1: Load a fresh network
        net = load_network(network_name)
        net_copy = copy.deepcopy(net)

        # Step 2: Call LLM to generate mutation code
        llm_response = self._call_llm(description, network_name)

        # Step 3: Parse the response
        parsed = self._parse_response(llm_response)
        if parsed is None:
            return {
                "net": net,
                "ground_truth": None,
                "generated_code": "",
                "generation_status": "error",
                "error": f"Failed to parse LLM response: {llm_response[:500]}",
                "response_type": "full_diagnosis",
                "text_answer": "",
            }

        mutation_code = parsed.get("mutation_code", "")
        ground_truth_raw = parsed.get("ground_truth", {})
        response_type = parsed.get("response_type", "full_diagnosis")
        text_answer = parsed.get("text_answer", "")

        # Step 4: Execute the mutation code safely (if any)
        if mutation_code.strip():
            exec_result = execute_safely(mutation_code, net_copy, timeout=5)

            if not exec_result["success"]:
                return {
                    "net": net,
                    "ground_truth": None,
                    "generated_code": mutation_code,
                    "generation_status": "error",
                    "error": exec_result["error"],
                    "response_type": response_type,
                    "text_answer": text_answer,
                }
            net = exec_result["net"]

        # Step 5: Build ScenarioResult from ground truth
        affected = ground_truth_raw.get("affected_components", {})
        # Normalize affected_components — values can be lists or strings
        normalized_affected: dict[str, list[int]] = {}
        for key, val in affected.items():
            if isinstance(val, list):
                normalized_affected[key] = [
                    int(v) for v in val if isinstance(v, (int, float))
                ]
            else:
                normalized_affected[key] = []

        ground_truth = ScenarioResult(
            scenario_name="nl_generated",
            network_name=network_name,
            failure_type=ground_truth_raw.get("failure_type", "unknown"),
            root_causes=ground_truth_raw.get("root_causes", [description]),
            affected_components=normalized_affected,
            known_fix=ground_truth_raw.get("known_fix", "See diagnosis"),
            metadata={
                "user_description": description,
                "generated_code": mutation_code,
            },
        )

        return {
            "net": net,
            "ground_truth": ground_truth,
            "generated_code": mutation_code,
            "generation_status": "success",
            "error": None,
            "response_type": response_type,
            "text_answer": text_answer,
        }

    def _call_llm(self, description: str, network_name: str) -> str:
        """Call the LLM to generate mutation code."""
        network_info = _get_network_info(network_name)

        system_prompt = SYSTEM_PROMPT.format(network_info=network_info)

        # Build few-shot messages
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        for ex in FEW_SHOT_EXAMPLES:
            messages.append({
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(
                    network_name=ex["network"],
                    description=ex["description"],
                ),
            })
            messages.append({
                "role": "assistant",
                "content": json.dumps(ex["response"]),
            })

        # Add the actual user request
        messages.append({
            "role": "user",
            "content": USER_PROMPT_TEMPLATE.format(
                network_name=network_name,
                description=description,
            ),
        })

        try:
            completion = self.llm_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.2,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )
            return completion.choices[0].message.content
        except Exception as e:
            return json.dumps({
                "error": f"LLM call failed: {str(e)}",
                "response_type": "full_diagnosis",
                "text_answer": "",
                "mutation_code": "",
                "ground_truth": {
                    "failure_type": "unknown",
                    "root_causes": [f"LLM generation failed: {str(e)}"],
                    "affected_components": {},
                    "known_fix": "Retry with a different description",
                },
            })

    def _parse_response(self, response: str) -> dict | None:
        """Parse the LLM JSON response into mutation_code + ground_truth."""
        try:
            # Try direct JSON parse
            data = json.loads(response)
            if "mutation_code" in data and "ground_truth" in data:
                return data
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code fences
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if "mutation_code" in data and "ground_truth" in data:
                    return data
            except json.JSONDecodeError:
                pass

        return None

