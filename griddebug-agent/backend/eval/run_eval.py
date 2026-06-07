"""
Unified Evaluation Script for GridDebugAgent

Runs both baseline and agentic pipelines on all scenarios,
capturing all metrics in one pass:
- Latency (both pipelines)
- Component predictions (both pipelines)
- Fix success (agentic only)
- Ground truth for comparison
"""
import os
import sys
import json
import copy
import time
import warnings
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Suppress pandapower warnings and logging
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*Voltage controlling elements.*")

import logging
logging.getLogger("pandapower").setLevel(logging.ERROR)

import pandapower as pp
from openai import OpenAI

from scenarios import (
    NonConvergenceScenarios,
    VoltageViolationScenarios,
    ThermalOverloadScenarios,
    ContingencyFailureScenarios,
    NormalScenarios,
)
from agents.baseline import BaselineAgent
from agents.iterative_debugger import IterativeDebuggerAgent


# Scenario definitions
SCENARIO_FACTORIES = {
    "nonconvergence": NonConvergenceScenarios,
    "voltage": VoltageViolationScenarios,
    "thermal": ThermalOverloadScenarios,
    "contingency": ContingencyFailureScenarios,
    "normal": NormalScenarios,
}

SCENARIOS = [
    {"id": "normal_operation", "label": "Normal Operation", "category": "normal"},
    {"id": "extreme_load_scaling", "label": "Extreme Load Scaling (20x)", "category": "nonconvergence"},
    {"id": "all_generators_removed", "label": "All Generators Removed", "category": "nonconvergence"},
    {"id": "near_zero_impedance", "label": "Near-Zero Impedance Line", "category": "nonconvergence"},
    {"id": "disconnected_subnetwork", "label": "Disconnected Sub-Network", "category": "nonconvergence"},
    {"id": "heavy_loading_undervoltage", "label": "Heavy Loading Under-Voltage", "category": "voltage"},
    {"id": "excess_generation_overvoltage", "label": "Excess Generation Over-Voltage", "category": "voltage"},
    {"id": "reactive_imbalance", "label": "Reactive Power Imbalance", "category": "voltage"},
    {"id": "concentrated_loading", "label": "Concentrated Loading on Weak Bus", "category": "thermal"},
    {"id": "reduced_thermal_limits", "label": "Reduced Thermal Limits (30%)", "category": "thermal"},
    {"id": "topology_redirection", "label": "Topology Change Flow Redirection", "category": "thermal"},
    {"id": "line_contingency_overload", "label": "N-1 Line Contingency Overload", "category": "contingency"},
    {"id": "trafo_contingency_voltage", "label": "N-1 Trafo Contingency Voltage", "category": "contingency"},
]


def count_violations(net: pp.pandapowerNet) -> dict:
    """Count voltage and thermal violations in a network."""
    violations = {"voltage": 0, "thermal": 0, "total": 0, "buses": [], "lines": [], "trafos": []}

    if not getattr(net, "converged", False):
        return violations  # Returns with total=0

    # Voltage violations
    if hasattr(net, "res_bus") and not net.res_bus.empty:
        for idx, row in net.res_bus.iterrows():
            vm_pu = row.get("vm_pu", 1.0)
            min_vm = net.bus.at[idx, "min_vm_pu"] if "min_vm_pu" in net.bus.columns else 0.95
            max_vm = net.bus.at[idx, "max_vm_pu"] if "max_vm_pu" in net.bus.columns else 1.05
            if vm_pu < min_vm or vm_pu > max_vm:
                violations["voltage"] += 1
                violations["buses"].append(int(idx))

    # Thermal violations (lines)
    if hasattr(net, "res_line") and not net.res_line.empty:
        for idx, row in net.res_line.iterrows():
            loading = row.get("loading_percent", 0)
            if loading > 100:
                violations["thermal"] += 1
                violations["lines"].append(int(idx))

    # Thermal violations (trafos)
    if hasattr(net, "res_trafo") and not net.res_trafo.empty:
        for idx, row in net.res_trafo.iterrows():
            loading = row.get("loading_percent", 0)
            if loading > 100:
                violations["thermal"] += 1
                violations["trafos"].append(int(idx))

    violations["total"] = violations["voltage"] + violations["thermal"]
    return violations


def find_and_apply_scenario(scenario_id: str, network: str = "case14"):
    """Find and apply a scenario, returning (scenario_obj, ground_truth)."""
    entry = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if entry is None:
        raise ValueError(f"Unknown scenario: {scenario_id}")

    factory = SCENARIO_FACTORIES[entry["category"]]
    all_scenarios = factory.all_scenarios(network)

    for sc in all_scenarios:
        result = sc.apply()
        if result.scenario_name == scenario_id:
            return sc, result

    raise ValueError(f"Scenario '{scenario_id}' not found in factory")


def run_eval(network: str = "case14"):
    """Run full evaluation on all scenarios."""

    # Initialize LLM client and agents
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    llm_client = OpenAI(api_key=api_key)
    baseline_agent = BaselineAgent(llm_client=llm_client)
    agentic_agent = IterativeDebuggerAgent(llm_client=llm_client)

    results = []

    print(f"\n{'='*70}")
    print(f"Full Evaluation - Network: {network}")
    print(f"Running {len(SCENARIOS)} scenarios through baseline + agentic pipelines")
    print(f"{'='*70}\n")

    for i, scenario in enumerate(SCENARIOS):
        scenario_id = scenario["id"]
        category = scenario["category"]

        print(f"[{i+1}/{len(SCENARIOS)}] {scenario_id}")
        print(f"    Category: {category}")

        result = {
            "scenario_id": scenario_id,
            "category": category,
            "network": network,
        }

        try:
            # Apply scenario
            scenario_obj, ground_truth = find_and_apply_scenario(scenario_id, network)
            net = scenario_obj.net

            # Store ground truth
            result["ground_truth"] = {
                "failure_type": ground_truth.failure_type,
                "root_causes": ground_truth.root_causes,
                "affected_components": ground_truth.affected_components,
                "known_fix": ground_truth.known_fix,
                "metadata": ground_truth.metadata,
            }

            # Run power flow on original
            try:
                pp.runpp(net)
            except:
                pass

            # Get initial state
            initial_converged = getattr(net, "converged", False)
            initial_violations = count_violations(net)
            result["initial_state"] = {
                "converged": initial_converged,
                "violations": initial_violations,
            }

            # --- BASELINE PIPELINE ---
            print(f"    Running baseline...", end=" ", flush=True)
            net_baseline = copy.deepcopy(net)

            start_time = time.time()
            baseline_result = baseline_agent.diagnose(net_baseline, network_name=network)
            baseline_latency = (time.time() - start_time) * 1000  # ms

            baseline_structured = baseline_result.get("structured_output", {})
            baseline_components = baseline_structured.get("affected_components", {}) if baseline_structured else {}

            result["baseline"] = {
                "latency_ms": round(baseline_latency, 1),
                "predicted_components": baseline_components,
                "root_causes": baseline_structured.get("root_causes", []) if baseline_structured else [],
                "corrective_actions": baseline_structured.get("corrective_actions", []) if baseline_structured else [],
                "confidence": baseline_structured.get("confidence", "") if baseline_structured else "",
                "response": baseline_result.get("response", ""),
            }
            print(f"{baseline_latency:.0f}ms")

            # --- AGENTIC PIPELINE ---
            print(f"    Running agentic...", end=" ", flush=True)
            net_agentic = copy.deepcopy(net)

            start_time = time.time()
            agentic_result = agentic_agent.diagnose(net_agentic, network_name=network)
            agentic_latency = (time.time() - start_time) * 1000  # ms

            final_converged = agentic_result.get("final_converged", False)
            final_violations = count_violations(net_agentic)

            # Get fix_history and compute metrics
            fix_history = agentic_result.get("fix_history", [])
            tool_calls = len(fix_history)
            react_iterations = len(set(h["iteration"] for h in fix_history)) if fix_history else 0

            # Determine fix success
            violations_decreased = final_violations["total"] <= initial_violations["total"]
            fix_success = final_converged and (violations_decreased or initial_violations["total"] == 0)

            result["agentic"] = {
                "latency_ms": round(agentic_latency, 1),
                "react_iterations": react_iterations,
                "tool_calls": tool_calls,
                "final_converged": final_converged,
                "final_violations": final_violations,
                "fix_success": fix_success,
                "fix_history": fix_history,
                "initial_diagnosis": agentic_result.get("initial_diagnosis"),
                "final_state": agentic_result.get("final_state"),
                "evidence": agentic_result.get("evidence"),
                "response": agentic_result.get("response", ""),
                "failure_category": agentic_result.get("failure_category", ""),
            }

            status = "FIXED" if fix_success else "NOT FIXED"
            print(f"{agentic_latency:.0f}ms, {react_iterations} react, {tool_calls} tools, {status}")

        except Exception as e:
            print(f"    ERROR: {e}")
            result["error"] = str(e)

        results.append(result)
        print()

    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    output = {
        "network": network,
        "timestamp": datetime.now().isoformat(),
        "scenarios": results,
    }

    output_path = results_dir / f"full_eval_{network}.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"{'='*70}")
    print(f"Results saved to: {output_path}")
    print(f"{'='*70}\n")

    # Print summary
    print_summary(results)

    return results


def print_summary(results: list):
    """Print evaluation summary."""
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70 + "\n")

    # Latency comparison
    baseline_latencies = [r["baseline"]["latency_ms"] for r in results if "baseline" in r]
    agentic_latencies = [r["agentic"]["latency_ms"] for r in results if "agentic" in r]

    if baseline_latencies:
        print(f"Baseline Latency:  avg={sum(baseline_latencies)/len(baseline_latencies):.0f}ms, "
              f"min={min(baseline_latencies):.0f}ms, max={max(baseline_latencies):.0f}ms")
    if agentic_latencies:
        print(f"Agentic Latency:   avg={sum(agentic_latencies)/len(agentic_latencies):.0f}ms, "
              f"min={min(agentic_latencies):.0f}ms, max={max(agentic_latencies):.0f}ms")

    # Fix success rate
    agentic_results = [r for r in results if "agentic" in r]
    fix_successes = sum(1 for r in agentic_results if r["agentic"].get("fix_success", False))
    if agentic_results:
        print(f"\nFix Success Rate:  {fix_successes}/{len(agentic_results)} "
              f"({fix_successes/len(agentic_results)*100:.1f}%)")
    else:
        print("\nFix Success Rate:  No agentic results")

    # By category
    categories = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"total": 0, "fix_success": 0}
        categories[cat]["total"] += 1
        if "agentic" in r and r["agentic"].get("fix_success", False):
            categories[cat]["fix_success"] += 1

    print("\nBy Category:")
    for cat, stats in sorted(categories.items()):
        rate = stats["fix_success"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {cat}: {stats['fix_success']}/{stats['total']} ({rate:.0f}%)")


def generate_report(results_path: str = None):
    """Generate markdown report from saved results."""
    if results_path is None:
        results_path = Path(__file__).parent / "results" / "full_eval_case14.json"

    with open(results_path) as f:
        data = json.load(f)

    print("\n# Evaluation Results\n")
    print(f"Network: {data['network']}")
    print(f"Timestamp: {data['timestamp']}\n")

    # Latency table
    print("## Latency Comparison\n")
    print("| Scenario | Category | Baseline (ms) | Agentic (ms) | Speedup |")
    print("|----------|----------|---------------|--------------|---------|")

    for r in data["scenarios"]:
        if "error" in r or "baseline" not in r or "agentic" not in r:
            continue
        baseline_ms = r["baseline"]["latency_ms"]
        agentic_ms = r["agentic"]["latency_ms"]
        speedup = f"{baseline_ms/agentic_ms:.2f}x" if agentic_ms > 0 else "N/A"
        print(f"| {r['scenario_id']} | {r['category']} | {baseline_ms:.0f} | {agentic_ms:.0f} | {speedup} |")

    # Fix success table
    print("\n## Fix Success Rate (Agentic Only)\n")
    print("| Scenario | Category | Initial Conv | Final Conv | Violations | Success |")
    print("|----------|----------|--------------|------------|------------|---------|")

    for r in data["scenarios"]:
        if "error" in r or "agentic" not in r or "initial_state" not in r:
            continue
        init_conv = r["initial_state"]["converged"]
        final_conv = r["agentic"].get("final_converged", False)
        init_viol = r["initial_state"]["violations"].get("total", 0)
        final_viol = r["agentic"].get("final_violations", {}).get("total", 0)
        success = "Yes" if r["agentic"].get("fix_success", False) else "No"
        print(f"| {r['scenario_id']} | {r['category']} | {init_conv} | {final_conv} | {init_viol}->{final_viol} | {success} |")

    # Summary stats
    results = data["scenarios"]
    baseline_latencies = [r["baseline"]["latency_ms"] for r in results if "baseline" in r and "error" not in r]
    agentic_latencies = [r["agentic"]["latency_ms"] for r in results if "agentic" in r and "error" not in r]
    fix_successes = sum(1 for r in results if "agentic" in r and r["agentic"].get("fix_success", False))
    total = len([r for r in results if "agentic" in r and "error" not in r])

    print("\n## Summary\n")
    if baseline_latencies:
        print(f"- **Baseline avg latency:** {sum(baseline_latencies)/len(baseline_latencies):.0f}ms")
    if agentic_latencies:
        print(f"- **Agentic avg latency:** {sum(agentic_latencies)/len(agentic_latencies):.0f}ms")
    if total > 0:
        print(f"- **Fix success rate:** {fix_successes}/{total} ({fix_successes/total*100:.1f}%)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run full evaluation")
    parser.add_argument("--network", default="case14", help="Network to evaluate on")
    parser.add_argument("--report", action="store_true", help="Generate report from saved results")

    args = parser.parse_args()

    if args.report:
        generate_report()
    else:
        run_eval(network=args.network)
