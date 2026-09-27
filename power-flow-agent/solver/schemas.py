"""Core data schemas used across solver, LLM tools, and UI."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ViolationType(str, Enum):
    OVERVOLTAGE = "overvoltage"
    UNDERVOLTAGE = "undervoltage"
    THERMAL_OVERLOAD = "thermal"


class BusVoltage(BaseModel):
    bus_id: int = Field(description="Bus ID (display ID)")
    vm_pu: float = Field(description="Voltage magnitude in p.u.")
    va_deg: float = Field(description="Voltage angle in degrees")
    is_violation: bool = Field(default=False, description="Whether voltage violates limits")
    violation_type: Optional[ViolationType] = Field(default=None, description="Violation type if any")


class LineFlow(BaseModel):
    line_id: int = Field(description="Unique branch ID (line or mapped trafo)")
    from_bus: int = Field(description="From bus display ID")
    to_bus: int = Field(description="To bus display ID")
    p_from_mw: float = Field(description="Active power from-side (MW)")
    q_from_mvar: float = Field(description="Reactive power from-side (Mvar)")
    loading_percent: float = Field(description="Branch loading percent")
    is_violation: bool = Field(default=False, description="Whether thermal loading violates limit")


class PowerFlowResult(BaseModel):
    case_name: str = Field(description="Case name, e.g. case14")
    converged: bool = Field(description="Whether solution converged")

    bus_voltages: list[BusVoltage] = Field(default_factory=list)
    line_flows: list[LineFlow] = Field(default_factory=list)

    total_generation_mw: float = Field(description="Total generation MW")
    total_load_mw: float = Field(description="Total load MW")
    total_loss_mw: float = Field(description="Total active losses MW")

    voltage_violations: list[BusVoltage] = Field(default_factory=list)
    thermal_violations: list[LineFlow] = Field(default_factory=list)

    summary_text: str = Field(default="")

    solver_backend: str = Field(default="pandapower", description="result backend: pandapower | llm_only")
    llm_prompt: Optional[str] = Field(default=None, description="raw prompt sent to LLM-only solver")
    llm_response: Optional[str] = Field(default=None, description="raw response returned by LLM-only solver")

    def model_post_init(self, __context: Any) -> None:
        if not self.voltage_violations and self.bus_voltages:
            self.voltage_violations = [bv for bv in self.bus_voltages if bv.is_violation]
        if not self.thermal_violations and self.line_flows:
            self.thermal_violations = [lf for lf in self.line_flows if lf.is_violation]


class NetworkInfo(BaseModel):
    case_name: str
    n_buses: int
    n_generators: int
    n_lines: int
    n_loads: int
    total_load_mw: float
    total_gen_capacity_mw: float


class ContingencyOutcome(BaseModel):
    branch_id: int
    branch_type: str
    from_bus: int
    to_bus: int

    converged: bool
    n_voltage_violations: int
    n_thermal_violations: int
    delta_voltage_violations: int = 0
    delta_thermal_violations: int = 0

    worst_vm_pu: Optional[float] = None
    worst_loading_percent: Optional[float] = None

    score: float
    notes: str = ""


class RemedialAction(BaseModel):
    action: str
    description: str
    parameters: dict
    predicted_risk: float
    risk_reduction: float
    preview_result: Optional[PowerFlowResult] = None


class RemedialPlan(BaseModel):
    case_name: str
    base_risk: float
    actions: list[RemedialAction] = Field(default_factory=list)
    summary_text: str = ""


class N1Report(BaseModel):
    case_name: str
    base_converged: bool
    top_k: int
    criteria: str
    results: list[ContingencyOutcome] = Field(default_factory=list)
    summary_text: str = ""


class Modification(BaseModel):
    action: str
    description: str
    parameters: dict[str, Any]


class SessionState(BaseModel):
    active_case: Optional[str] = None
    network_info: Optional[NetworkInfo] = None
    last_result: Optional[PowerFlowResult] = None

    last_n1_report: Optional[N1Report] = None
    last_remedial_plan: Optional[RemedialPlan] = None

    modification_log: list[Modification] = Field(default_factory=list)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
