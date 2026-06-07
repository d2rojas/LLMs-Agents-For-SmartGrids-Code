# Config

Configuration for site constraints, time-of-use (TOU) rates, and experiments. Used by the optimizer, constraint checker, baseline, and evaluation so all components share the same numbers and runs are reproducible.

## `site.py` — Site and TOU

- **SiteConfig**: Site-level constraints for one day.
  - `P_max_kw`: Site power cap (kW). Either a scalar (constant for all steps) or an array of length `n_steps` for a time-varying cap. Constraint: sum of charging power at each step must be ≤ cap at that step.
  - `n_steps`: Number of time steps in the horizon (indices 0 .. n_steps−1).
  - `dt_hours`: Duration of each time step in hours (e.g. 0.25 for 15 min).
  - `get_P_max_at_step(t)`: Returns the power cap at time step `t` (kW). Handles both scalar and array `P_max_kw`.

- **TOUConfig**: Time-of-use energy rates ($/kWh) per time step.
  - `rates_per_kwh`: 1D array of length `n_steps`; cost in $/kWh for each step. The objective minimizes total energy cost = ∑_t c(t) × power_t × dt.
  - `n_steps`: Property returning `len(rates_per_kwh)`; must match the day horizon.

- **default_tou_rates(n_steps, peak_price=0.45, off_peak_price=0.12)**: Builds a TOU rate vector of length `n_steps` with a single peak window. Step 0 = midnight; peak is 4pm–9pm (higher price), rest is off-peak. Returns a numpy array suitable for `TOUConfig(rates_per_kwh=...)`.

## Experiments

- **Site constraints**: `P_max(t)`, per-charger limits, time step ∆ (e.g. 5 or 15 min) — see `SiteConfig`.
- **TOU rates**: `c(t)` vector per experiment (fixed per run; §5) — see `TOUConfig` and `default_tou_rates`.
- **Experiments**: 5+ days with varying congestion; reference to ACN-Data site/date filters (see `config/experiments/`).
