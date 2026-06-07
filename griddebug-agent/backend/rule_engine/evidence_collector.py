"""
Evidence collector for power flow simulation results.

Gathers all relevant solver outputs into a structured EvidenceReport
that can be consumed by the rule engine and formatted for LLM prompting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import pandapower as pp


@dataclass
class EvidenceReport:
    """Structured collection of solver evidence from a pandapower network."""

    # ── Convergence ────────────────────────────────────────────────
    converged: bool = False
    iterations: int | None = None

    # ── Bus voltages ───────────────────────────────────────────────
    bus_count: int = 0
    voltage_min_pu: float | None = None
    voltage_max_pu: float | None = None
    voltage_mean_pu: float | None = None
    undervoltage_buses: list[dict] = field(default_factory=list)
    overvoltage_buses: list[dict] = field(default_factory=list)

    # ── Line loading ───────────────────────────────────────────────
    line_count: int = 0
    max_line_loading_pct: float | None = None
    overloaded_lines: list[dict] = field(default_factory=list)

    # ── Transformer loading ────────────────────────────────────────
    trafo_count: int = 0
    max_trafo_loading_pct: float | None = None
    overloaded_trafos: list[dict] = field(default_factory=list)

    # ── Generation ─────────────────────────────────────────────────
    gen_count: int = 0
    total_gen_p_mw: float = 0.0
    total_gen_q_mvar: float = 0.0
    gens_at_q_limit: list[dict] = field(default_factory=list)

    # ── Loads ──────────────────────────────────────────────────────
    total_load_p_mw: float = 0.0
    total_load_q_mvar: float = 0.0

    # ── Input data (available even without convergence) ────────────
    input_load_count: int = 0
    input_load_details: list[dict] = field(default_factory=list)
    input_gen_count: int = 0
    input_gen_details: list[dict] = field(default_factory=list)
    input_ext_grid_count: int = 0
    input_gen_capacity_mw: float = 0.0

    # ── Power balance ──────────────────────────────────────────────
    active_power_mismatch_mw: float = 0.0
    reactive_power_mismatch_mvar: float = 0.0

    # ── Diagnostic results ─────────────────────────────────────────
    diagnostic_results: dict[str, Any] = field(default_factory=dict)

    # ── Network topology ───────────────────────────────────────────
    disconnected_buses: list[int] = field(default_factory=list)
    isolated_elements: dict[str, list[int]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to a plain dict for serialization or LLM prompting."""
        return {
            "convergence": {
                "converged": self.converged,
                "iterations": self.iterations,
            },
            "voltages": {
                "bus_count": self.bus_count,
                "min_pu": self.voltage_min_pu,
                "max_pu": self.voltage_max_pu,
                "mean_pu": self.voltage_mean_pu,
                "undervoltage_buses": self.undervoltage_buses,
                "overvoltage_buses": self.overvoltage_buses,
            },
            "line_loading": {
                "line_count": self.line_count,
                "max_loading_pct": self.max_line_loading_pct,
                "overloaded_lines": self.overloaded_lines,
            },
            "trafo_loading": {
                "trafo_count": self.trafo_count,
                "max_loading_pct": self.max_trafo_loading_pct,
                "overloaded_trafos": self.overloaded_trafos,
            },
            "generation": {
                "gen_count": self.gen_count,
                "total_p_mw": self.total_gen_p_mw,
                "total_q_mvar": self.total_gen_q_mvar,
                "at_q_limit": self.gens_at_q_limit,
            },
            "load": {
                "total_p_mw": self.total_load_p_mw,
                "total_q_mvar": self.total_load_q_mvar,
            },
            "power_balance": {
                "active_mismatch_mw": self.active_power_mismatch_mw,
                "reactive_mismatch_mvar": self.reactive_power_mismatch_mvar,
            },
            "topology": {
                "disconnected_buses": self.disconnected_buses,
                "isolated_elements": self.isolated_elements,
            },
            "diagnostics": self.diagnostic_results,
        }

    def to_text(self) -> str:
        """Format as a human-readable/LLM-readable text summary."""
        lines = ["=" * 60, "POWER FLOW EVIDENCE REPORT", "=" * 60]

        # ── Convergence status ──
        lines.append(f"\nConvergence: {'YES' if self.converged else 'NO — POWER FLOW DID NOT CONVERGE'}")
        if self.iterations:
            lines.append(f"Iterations: {self.iterations}")

        if not self.converged:
            lines.append("\n⚠️  NON-CONVERGENCE DETECTED")
            lines.append("  The Newton-Raphson solver failed to find a feasible operating point.")
            lines.append("  Result tables (voltages, line loadings) are UNAVAILABLE.")
            lines.append("  The following INPUT DATA is provided for root cause analysis:")

        # ── Input load/gen data (always available) ──
        lines.append(f"\n── INPUT: Load Demand ──")
        lines.append(f"  Total active load (P):   {self.total_load_p_mw:.1f} MW")
        lines.append(f"  Total reactive load (Q): {self.total_load_q_mvar:.1f} Mvar")
        lines.append(f"  Number of in-service loads: {self.input_load_count}")
        if self.input_load_details:
            lines.append(f"  Top loads by MW:")
            for ld in self.input_load_details[:8]:
                lines.append(f"    Load {ld['index']} at bus {ld['bus']}: {ld['p_mw']:.1f} MW, {ld['q_mvar']:.1f} Mvar")

        lines.append(f"\n── INPUT: Generation Capacity ──")
        lines.append(f"  Ext grid count:  {self.input_ext_grid_count}")
        lines.append(f"  Generator count: {self.input_gen_count} (in-service)")
        lines.append(f"  Total gen capacity (P_max): {self.input_gen_capacity_mw:.1f} MW")
        if self.input_gen_details:
            for g in self.input_gen_details:
                lines.append(f"    Gen {g['index']} at bus {g['bus']}: p_mw={g['p_mw']:.1f}, "
                             f"in_service={g['in_service']}")

        # ── Load vs generation comparison ──
        lines.append(f"\n── LOAD vs GENERATION COMPARISON ──")
        if self.input_gen_capacity_mw > 0:
            ratio = self.total_load_p_mw / self.input_gen_capacity_mw
            lines.append(f"  Load/GenCapacity ratio: {ratio:.2f}x")
            if ratio > 1.5:
                lines.append(f"  ⚠️  LOAD EXCEEDS GENERATION CAPACITY by {(ratio-1)*100:.0f}%")
        elif self.input_ext_grid_count > 0:
            lines.append(f"  Generation via ext_grid (infinite bus) — capacity not bounded")
        else:
            lines.append(f"  ⚠️  NO GENERATION SOURCES AVAILABLE")
        lines.append(f"  Demand-supply gap: {self.total_load_p_mw - self.input_gen_capacity_mw:.1f} MW")

        # ── Result data (only if converged) ──
        if self.converged:
            lines.append(f"\n── RESULT: Bus Voltages ({self.bus_count} buses) ──")
            if self.voltage_min_pu is not None:
                lines.append(f"  Range: {self.voltage_min_pu:.4f} – {self.voltage_max_pu:.4f} pu")
                lines.append(f"  Mean:  {self.voltage_mean_pu:.4f} pu")
            if self.undervoltage_buses:
                lines.append(f"  Under-voltage (under bus-specific limit or default 0.95 pu): {len(self.undervoltage_buses)} buses")
                for b in self.undervoltage_buses[:5]:
                    limit_str = f" (limit: {b['limit']:.4f} pu)" if 'limit' in b else ""
                    lines.append(f"    Bus {b['index']}: {b['vm_pu']:.4f} pu{limit_str}")
            if self.overvoltage_buses:
                lines.append(f"  Over-voltage (over bus-specific limit or default 1.05 pu): {len(self.overvoltage_buses)} buses")
                for b in self.overvoltage_buses[:5]:
                    limit_str = f" (limit: {b['limit']:.4f} pu)" if 'limit' in b else ""
                    lines.append(f"    Bus {b['index']}: {b['vm_pu']:.4f} pu{limit_str}")

            lines.append(f"\n── RESULT: Line Loading ({self.line_count} lines) ──")
            if self.max_line_loading_pct is not None:
                lines.append(f"  Max loading: {self.max_line_loading_pct:.1f}%")
            if self.overloaded_lines:
                lines.append(f"  Overloaded (>100%): {len(self.overloaded_lines)} lines")
                for l in self.overloaded_lines[:5]:
                    lines.append(f"    Line {l['index']}: {l['loading_pct']:.1f}%")

            lines.append(f"\n── RESULT: Power Balance ──")
            lines.append(f"  Total generation: {self.total_gen_p_mw:.1f} MW, {self.total_gen_q_mvar:.1f} Mvar")
            lines.append(f"  Total load:       {self.total_load_p_mw:.1f} MW, {self.total_load_q_mvar:.1f} Mvar")
            lines.append(f"  Mismatch:         {self.active_power_mismatch_mw:.2f} MW, "
                          f"{self.reactive_power_mismatch_mvar:.2f} Mvar")

        # ── Topology issues ──
        if self.disconnected_buses:
            lines.append(f"\n── TOPOLOGY: Disconnected buses ──")
            lines.append(f"  {len(self.disconnected_buses)} buses disconnected: {self.disconnected_buses[:10]}")

        # ── Diagnostics (filtered) ──
        if self.diagnostic_results:
            lines.append(f"\n── Pandapower Diagnostics ──")
            # Filter out noise warnings
            noise_warnings = {"test_continuous_bus_indices", "test_bus_indices_type"}
            for name, result in self.diagnostic_results.items():
                if result and name not in noise_warnings:
                    lines.append(f"  {name}: ISSUES FOUND")

        lines.append("=" * 60)
        return "\n".join(lines)


class EvidenceCollector:
    """Collects solver evidence from a pandapower network."""

    def __init__(self, v_min: float = 0.95, v_max: float = 1.05, max_loading: float = 100.0):
        self.v_min = v_min
        self.v_max = v_max
        self.max_loading = max_loading

    def collect(self, net: pp.pandapowerNet) -> EvidenceReport:
        """
        Collect all available evidence from the network after a power
        flow attempt. Works whether or not PF converged.
        """
        report = EvidenceReport()

        # ── Convergence ────────────────────────────────────────────
        report.converged = getattr(net, "converged", False)

        # ── Network counts ─────────────────────────────────────────
        report.bus_count = len(net.bus)
        report.line_count = len(net.line)
        report.trafo_count = len(net.trafo)
        report.gen_count = len(net.gen) + len(net.sgen) + len(net.ext_grid)

        # ── Load totals ────────────────────────────────────────────
        in_service_loads = net.load[net.load["in_service"]]
        report.total_load_p_mw = float(in_service_loads["p_mw"].sum())
        report.total_load_q_mvar = float(in_service_loads["q_mvar"].sum())

        # ── Input data (always available) ──────────────────────────
        self._collect_input_data(net, report)

        # ── Results (only if converged) ────────────────────────────
        if report.converged and len(net.res_bus) > 0:
            self._collect_bus_results(net, report)
            self._collect_line_results(net, report)
            self._collect_trafo_results(net, report)
            self._collect_gen_results(net, report)
            self._compute_power_balance(report)

        # ── Diagnostics (works even without convergence) ───────────
        self._collect_diagnostics(net, report)

        return report

    def _collect_bus_results(self, net: pp.pandapowerNet, report: EvidenceReport) -> None:
        res = net.res_bus
        bus_df = net.bus
        report.voltage_min_pu = float(res["vm_pu"].min())
        report.voltage_max_pu = float(res["vm_pu"].max())
        report.voltage_mean_pu = float(res["vm_pu"].mean())

        for idx, row in res.iterrows():
            vm_pu = float(row["vm_pu"])
            
            # Use specific limit if available, fallback to global
            bus_v_min = bus_df.at[idx, "min_vm_pu"] if "min_vm_pu" in bus_df.columns and pd.notna(bus_df.at[idx, "min_vm_pu"]) else self.v_min
            bus_v_max = bus_df.at[idx, "max_vm_pu"] if "max_vm_pu" in bus_df.columns and pd.notna(bus_df.at[idx, "max_vm_pu"]) else self.v_max
            
            if vm_pu < bus_v_min:
                report.undervoltage_buses.append({
                    "index": int(idx),
                    "vm_pu": round(vm_pu, 4),
                    "limit": bus_v_min,
                })
            elif vm_pu > bus_v_max:
                report.overvoltage_buses.append({
                    "index": int(idx),
                    "vm_pu": round(vm_pu, 4),
                    "limit": bus_v_max,
                })

    def _collect_line_results(self, net: pp.pandapowerNet, report: EvidenceReport) -> None:
        res = net.res_line
        if "loading_percent" in res.columns and len(res) > 0:
            report.max_line_loading_pct = float(res["loading_percent"].max())
            for idx, row in res[res["loading_percent"] > self.max_loading].iterrows():
                report.overloaded_lines.append({
                    "index": int(idx),
                    "loading_pct": round(float(row["loading_percent"]), 1),
                    "from_bus": int(net.line.at[idx, "from_bus"]),
                    "to_bus": int(net.line.at[idx, "to_bus"]),
                })

    def _collect_trafo_results(self, net: pp.pandapowerNet, report: EvidenceReport) -> None:
        if len(net.trafo) == 0:
            return
        res = net.res_trafo
        if "loading_percent" in res.columns and len(res) > 0:
            report.max_trafo_loading_pct = float(res["loading_percent"].max())
            for idx, row in res[res["loading_percent"] > self.max_loading].iterrows():
                report.overloaded_trafos.append({
                    "index": int(idx),
                    "loading_pct": round(float(row["loading_percent"]), 1),
                })

    def _collect_gen_results(self, net: pp.pandapowerNet, report: EvidenceReport) -> None:
        total_p = 0.0
        total_q = 0.0

        # Ext grid
        if len(net.res_ext_grid) > 0:
            total_p += float(net.res_ext_grid["p_mw"].sum())
            total_q += float(net.res_ext_grid["q_mvar"].sum())

        # Generators
        if len(net.res_gen) > 0:
            total_p += float(net.res_gen["p_mw"].sum())
            total_q += float(net.res_gen["q_mvar"].sum())

            # Check Q limits
            for idx, row in net.gen.iterrows():
                if idx in net.res_gen.index:
                    q_actual = net.res_gen.at[idx, "q_mvar"]
                    q_max = row.get("max_q_mvar", float("inf"))
                    q_min = row.get("min_q_mvar", float("-inf"))
                    if pd.notna(q_max) and q_actual >= q_max * 0.95:
                        report.gens_at_q_limit.append({
                            "index": int(idx),
                            "q_mvar": round(float(q_actual), 2),
                            "limit": "max",
                        })
                    elif pd.notna(q_min) and q_actual <= q_min * 0.95:
                        report.gens_at_q_limit.append({
                            "index": int(idx),
                            "q_mvar": round(float(q_actual), 2),
                            "limit": "min",
                        })

        # Static generators
        if len(net.res_sgen) > 0:
            total_p += float(net.res_sgen["p_mw"].sum())
            total_q += float(net.res_sgen["q_mvar"].sum())

        report.total_gen_p_mw = round(total_p, 2)
        report.total_gen_q_mvar = round(total_q, 2)

    def _collect_input_data(self, net: pp.pandapowerNet, report: EvidenceReport) -> None:
        """Collect input load/gen data from the model (always available)."""
        import pandas as pd

        # Load details
        in_service_loads = net.load[net.load["in_service"]]
        report.input_load_count = len(in_service_loads)
        load_sorted = in_service_loads.sort_values("p_mw", ascending=False)
        for idx, row in load_sorted.head(15).iterrows():
            report.input_load_details.append({
                "index": int(idx),
                "bus": int(row["bus"]),
                "p_mw": round(float(row["p_mw"]), 2),
                "q_mvar": round(float(row["q_mvar"]), 2),
            })

        # Gen details
        in_service_gens = net.gen[net.gen["in_service"]] if len(net.gen) > 0 else pd.DataFrame()
        report.input_gen_count = len(in_service_gens)
        report.input_ext_grid_count = len(net.ext_grid[net.ext_grid["in_service"]])

        gen_capacity = 0.0
        for idx, row in in_service_gens.iterrows():
            p_mw = float(row.get("p_mw", 0))
            max_p = float(row.get("max_p_mw", p_mw)) if pd.notna(row.get("max_p_mw")) else p_mw
            gen_capacity += max_p
            report.input_gen_details.append({
                "index": int(idx),
                "bus": int(row["bus"]),
                "p_mw": round(p_mw, 2),
                "max_p_mw": round(max_p, 2),
                "in_service": bool(row["in_service"]),
            })
        report.input_gen_capacity_mw = round(gen_capacity, 2)

    def _compute_power_balance(self, report: EvidenceReport) -> None:
        report.active_power_mismatch_mw = round(
            report.total_gen_p_mw - report.total_load_p_mw, 2
        )
        report.reactive_power_mismatch_mvar = round(
            report.total_gen_q_mvar - report.total_load_q_mvar, 2
        )

    def _collect_diagnostics(self, net: pp.pandapowerNet, report: EvidenceReport) -> None:
        """Run pandapower diagnostic and store results."""
        try:
            result = pp.diagnostic(
                net,
                report_style=None,
                warnings_only=True,
                return_result_dict=True,
            )
            if isinstance(result, dict):
                report.diagnostic_results = result
        except Exception:
            # Diagnostics can fail on heavily corrupted networks
            report.diagnostic_results = {"error": "Diagnostic failed"}
