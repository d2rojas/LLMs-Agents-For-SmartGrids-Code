# EVAgent — Architecture and Module Reference

How the EV charging scheduler is organized internally. For setup and run
instructions, see the project [`README.md`](../README.md).

## Pipelines

### Agentic pipeline (`agent/`)

1. **Plan**: Parse user request → objective, horizon, constraints, session params.
2. **Optimize**: Formulate and solve (CVXPY) cost-minimization with slack; compute peak load.
3. **Validate**: Constraint checker → feasibility, unmet energy, peak load.
4. **Refine**: On parsing/implementation errors, fix structured representation and re-solve.
5. **Explain**: Extract schedule-derived facts; generate NL explanation grounded in computed artifacts.

### LLM-only baseline (`baseline/`)

- Single-shot: LLM receives facility constraints, session data, and objective; outputs full charging schedule.
- Evaluated for cost, unmet energy, and constraint violations.
- If repair is used: one projection step; metrics are reported before and after.

## Data format (`data/format/`)

Defines the common data shape for one-day EV charging: **Session** and **DaySessions** in `schema.py`.

### Time convention

- Time is **discrete**: step indices `0 .. n_steps-1`.
- Each step has duration **`dt_hours`** (e.g. `0.25` for 15-minute intervals).
- Defaults: `DEFAULT_DT_HOURS = 0.25`, `DEFAULT_STEPS_PER_HOUR = 4`.

### Session (per EV visit)

| Field           | Type  | Description |
|----------------|-------|-------------|
| `session_id`   | str   | Unique id (e.g. ACN-Data sessionID). |
| `arrival_idx`  | int   | First time step when charging is allowed (inclusive). |
| `departure_idx`| int   | First time step when charging is no longer allowed (exclusive). |
| `energy_kwh`   | float | Requested energy to deliver (kWh). |
| `charger_id`   | str   | Assigned charger/station (e.g. spaceID). |
| `max_power_kw` | float | Max charging power for this session (kW). |

Charging is allowed only for steps `t` in **[arrival_idx, departure_idx)**. Power must satisfy `0 ≤ p_i(t) ≤ max_power_kw`.

### DaySessions (one day)

- **`sessions`**: list of `Session` (order is fixed for schedule matrices).
- **`n_steps`**: number of time steps in the horizon.
- **`dt_hours`**: duration of each step (hours).

Every session must have `departure_idx ≤ n_steps`. Units: power in **kW**, energy in **kWh**.

## Data loader (`data/loader/`)

Loads sessions from the Caltech ACN-Data API and maps them to the standardized format.

- **API**: Requests use the Eve API at `https://ev.caltech.edu/api/v1/`. The `where` parameter is **MongoDB-style JSON** (e.g. `{"connectionTime": {"$gte": "RFC1123"}, {"$lte": "..."}}`) and is URL-encoded. This matches the API; the acnportal `DataClient` uses a different format and is not used for the request.
- **Auth**: `ACN_DATA_API_TOKEN` from environment or `.env`; passed as HTTP Basic auth (token as username, empty password).
- **Query window**: Midnight-to-midnight **UTC** for the requested calendar day. Pagination via `_links.next` is followed.
- **`load_sessions(site_id, day_date, api_token=None, n_steps=96, dt_hours=0.25)`**: Returns `DaySessions`. Raises `ValueError` if token is missing or API returns an error.
- **`raw_session_to_standard(raw, day_start_utc, dt_hours, n_steps)`**: Maps one API session dict to `Session` (connectionTime/disconnectTime → arrival_idx/departure_idx, kWhDelivered → energy_kwh, sessionID, spaceID, max power).

No synthetic data; an API key is required.

## Configuration (`config/`)

Configuration for site constraints and time-of-use (TOU) rates. Used by the optimizer, constraint checker, baseline, and evaluation so all components share the same numbers and runs are reproducible.

- **SiteConfig**: Site-level constraints for one day.
  - `P_max_kw`: Site power cap (kW). Either a scalar (constant for all steps) or an array of length `n_steps` for a time-varying cap. Constraint: sum of charging power at each step must be ≤ cap at that step.
  - `n_steps`: Number of time steps in the horizon (indices 0 .. n_steps−1).
  - `dt_hours`: Duration of each time step in hours (e.g. 0.25 for 15 min).
  - `get_P_max_at_step(t)`: Returns the power cap at time step `t` (kW). Handles both scalar and array `P_max_kw`.
- **TOUConfig**: Time-of-use energy rates ($/kWh) per time step.
  - `rates_per_kwh`: 1D array of length `n_steps`; cost in $/kWh for each step. The objective minimizes total energy cost = ∑_t c(t) × power_t × dt.
  - `n_steps`: Property returning `len(rates_per_kwh)`; must match the day horizon.
- **default_tou_rates(n_steps, peak_price=0.45, off_peak_price=0.12)**: Builds a TOU rate vector of length `n_steps` with a single peak window. Step 0 = midnight; peak is 4pm–9pm (higher price), rest is off-peak. Returns a numpy array suitable for `TOUConfig(rates_per_kwh=...)`.

## Optimization (`optimization/`)

Implemented in `solver.py` (CVXPY).

- **Decision variables**: `p[i,t]` (kW) per session per time step; `u[i]` (kWh) slack/unmet per session.
- **Objective**: min ∑_t c(t)·(∑_i p_i(t))·∆ + M·∑_i u_i; report peak = max_t ∑_i p_i(t).
- **Constraints**: Availability (p=0 outside [arrival, departure)), per-charger (p ≤ max_power_kw), site cap (∑_i p_i(t) ≤ P_max(t)), energy (delivered + u_i = E_i).
- **API**: `solve(day, site, tou, penalty_unmet=1e6)` → `SolveResult` with `schedule`, `total_cost_usd`, `unmet_energy_kwh`, `peak_load_kw`, `success`, `message`.

Called by the Phase A script and by the agent Optimize step.

## Constraint checker (`constraints/`)

Implemented in `checker.py`. Verifies a schedule (shape `n_sessions × n_steps`, power in kW) against sessions and site config.

- **Availability**: `p_i(t) = 0` for `t ∉ [a_i, d_i)`.
- **Per-charger limits**: `0 ≤ p_i(t) ≤ p̄_i`.
- **Site power cap**: `∑_i p_i(t) ≤ P_max(t)` at each `t`.
- **Energy**: Delivered = ∑_t p_i(t)·∆; no over-delivery; unmet = max(0, E_i − delivered).
- **API**: `check(schedule, day, site, dt_hours=None, tol=None)` → `CheckResult` with `feasible`, `violations` (list of `Violation`: kind, session_id, time_step, message), `unmet_energy_kwh`, `peak_load_kw`. `DEFAULT_TOL = 1e-5`; override with `tol` for stricter/looser checks.

Used by the Phase A script, baseline (optional repair), and agent (Validate step).

## Evaluation (`evaluation/`)

- **`total_cost(schedule, tou, dt_hours)`**: Total energy cost ($) = ∑_t c(t)·(∑_i p_i(t))·dt.
- **`total_unmet_kwh(schedule, day, dt_hours)`**: Sum over sessions of max(0, E_i − delivered_i).
- **`peak_load_kw(schedule)`**: max_t ∑_i p_i(t).
- **`pct_fully_served(schedule, day, dt_hours)`**: % of sessions with delivered ≥ requested (0–100).
- **`charge_asap_schedule(day, site_p_max)`**: Uncontrolled baseline (max rate from arrival until E_i met); used for % cost reduction.
- **`compute_metrics(...)`**: Returns `Metrics` (cost, unmet, peak, violation_count, pct_fully_served, optional cost_reduction_vs_uncontrolled_pct).
- **Faithfulness** (`evaluation/faithfulness/`): Verifies that numeric claims in generated explanations match the computed schedule.

## Visualization (`visualization/`)

- **`plot_schedule(schedule, day, save_path=None)`**: 2D heatmap — rows = sessions, columns = time step, color = power (kW). Saves PNG if `save_path` is set.
- **`plot_load_profile(schedule, day, save_path=None, title=None)`**: Line plot of total facility load (∑_i p_i(t)) vs time step. Optional title (e.g. cost/unmet summary).

Figures are closed after save to avoid memory growth.

## Tests (`tests/`)

- **`test_constraints.py`**: Feasible schedule plus one violation each for availability, per-charger, site-cap, and energy constraints.
- **`test_baseline_parse.py`**: LLM output resampling and schedule parsing.
- **`test_data_loader.py`**: ACN-Data format conversion and API response handling (skips live fetch if token not set).
- **`test_faithfulness.py`**: Claim extraction and ground-truth comparison for explanation faithfulness.
