"""Standardized session and day format for the EV charging pipeline.

Time is discrete: step indices 0 .. n_steps-1. Each step has duration dt_hours (e.g. 0.25 for 15 min).
Session availability is the half-open interval [arrival_idx, departure_idx): charging is allowed
at steps t where arrival_idx <= t < departure_idx. Power is in kW, energy in kWh.
Used by the data loader, constraint checker, optimization solver, baseline, and agent.
"""

from dataclasses import dataclass
from typing import List


# Default time resolution: 15-minute intervals (used when not specified)
DEFAULT_DT_HOURS = 0.25  # hours per step
DEFAULT_STEPS_PER_HOUR = 4  # steps per hour at 15-min resolution


@dataclass(frozen=True)
class Session:
    """One charging session (one EV visit to a charger).

    Attributes:
        session_id: Unique identifier (e.g. from ACN-Data sessionID).
        arrival_idx: First time step index when charging is allowed (inclusive).
        departure_idx: First time step index when charging is no longer allowed (exclusive).
            Charging is allowed only for t in [arrival_idx, departure_idx).
        energy_kwh: Requested energy to deliver (kWh).
        charger_id: Assigned charger/station ID (e.g. ACN-Data spaceID).
        max_power_kw: Maximum charging power for this session (kW); 0 <= p_i(t) <= this value.
    """

    session_id: str
    arrival_idx: int
    departure_idx: int
    energy_kwh: float
    charger_id: str
    max_power_kw: float

    def __post_init__(self) -> None:
        """Validate session fields: indices non-negative and ordered, energy and max power positive."""
        if self.arrival_idx < 0:
            raise ValueError("arrival_idx must be non-negative")
        if self.departure_idx < 0:
            raise ValueError("departure_idx must be non-negative")
        if self.arrival_idx >= self.departure_idx:
            raise ValueError("arrival_idx must be less than departure_idx")
        if self.energy_kwh <= 0:
            raise ValueError("energy_kwh must be positive")
        if self.max_power_kw <= 0:
            raise ValueError("max_power_kw must be positive")

@dataclass
class DaySessions:
    """Sessions for a single day with a fixed time horizon.

    Attributes:
        sessions: List of Session in arbitrary order. Schedule matrices use the same order.
        n_steps: Number of time steps in the horizon (indices 0 .. n_steps-1).
        dt_hours: Duration of each time step in hours (e.g. 0.25 for 15-minute intervals).
    """

    sessions: List[Session]
    n_steps: int
    dt_hours: float = DEFAULT_DT_HOURS

    def __post_init__(self) -> None:
        """Validate horizon (n_steps, dt_hours) and that every session fits within the horizon."""
        if self.n_steps <= 0:
            raise ValueError("n_steps must be positive")
        if self.dt_hours <= 0:
            raise ValueError("dt_hours must be positive")
        for s in self.sessions:
            if s.departure_idx > self.n_steps:
                raise ValueError(
                    f"Session {s.session_id} departure_idx {s.departure_idx} exceeds n_steps {self.n_steps}"
                )
