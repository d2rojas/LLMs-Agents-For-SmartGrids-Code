"""Structured output schema for LLM-only blueprint mode."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PathAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    load_bus: int = Field(description="Load bus id (MATPOWER BUS_I, 1-based).")
    pd_mw: float = Field(description="Active load at load_bus in MW.")
    path_str: str = Field(
        description="A dash-separated string of bus IDs, e.g., '14-13-6-5-1'.",
    )


class BranchPdSum(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: int = Field(description="Branch line id, MATPOWER branch row number (1-based).")
    from_bus: int = Field(description="From bus id (MATPOWER BUS_I, 1-based).")
    to_bus: int = Field(description="To bus id (MATPOWER BUS_I, 1-based).")
    pd_sum_mw: float = Field(description="Summed routed Pd on this branch in MW.")


class DebugRoutingStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slack_bus: int = Field(description="Slack bus id (MATPOWER BUS_I, 1-based).")
    loss_factor_assumed: float = Field(description="Assumed loss factor used by heuristic routing.")
    path_assignments: list[PathAssignment] = Field(
        default_factory=list,
        max_length=30,
        description="Top 30 load-path assignments by Pd magnitude.",
    )
    branch_pd_sums: list[BranchPdSum] = Field(
        default_factory=list,
        max_length=50,
        description="Top 50 branch Pd sums by |pd_sum_mw| magnitude.",
    )


class TotalsSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_generation_mw: float
    total_load_mw: float
    total_loss_mw: float


class BusVoltageSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bus_id: int = Field(
        description="Must equal MATPOWER bus matrix BUS_I (1-based).",
    )
    vm_pu: float
    va_deg: float


class LineFlowSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: int = Field(
        description="Must equal MATPOWER branch matrix row number (1-based).",
    )
    from_bus: int = Field(description="MATPOWER BUS_I (1-based).")
    to_bus: int = Field(description="MATPOWER BUS_I (1-based).")
    p_from_mw: float
    q_from_mvar: float
    loading_percent: Optional[float] = Field(
        default=None,
        description="If RATE_A == 0 for this line_id, this field must be 0.0.",
    )


class VoltageViolationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bus_id: int = Field(description="Must equal MATPOWER BUS_I (1-based).")
    vm_pu: float
    type: Literal["overvoltage", "undervoltage"]


class ThermalViolationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: int = Field(description="MATPOWER branch row number (1-based).")
    from_bus: int = Field(description="MATPOWER BUS_I (1-based).")
    to_bus: int = Field(description="MATPOWER BUS_I (1-based).")
    loading_percent: float


class PowerFlowResultSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_name: str
    converged: bool
    totals: TotalsSchema
    bus_voltages: list[BusVoltageSchema] = Field(default_factory=list)
    line_flows: list[LineFlowSchema] = Field(default_factory=list)
    voltage_violations: list[VoltageViolationSchema] = Field(default_factory=list)
    thermal_violations: list[ThermalViolationSchema] = Field(default_factory=list)
    summary_text: str
    debug_routing_step: Optional[DebugRoutingStep] = None
