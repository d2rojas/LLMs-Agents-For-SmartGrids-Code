# Standardized session format

Defines the common data shape for one-day EV charging: **Session** and **DaySessions** in `schema.py`.

## Time convention

- Time is **discrete**: step indices `0 .. n_steps-1`.
- Each step has duration **`dt_hours`** (e.g. `0.25` for 15-minute intervals).
- Defaults: `DEFAULT_DT_HOURS = 0.25`, `DEFAULT_STEPS_PER_HOUR = 4`.

## Session (per EV visit)

| Field           | Type  | Description |
|----------------|-------|-------------|
| `session_id`   | str   | Unique id (e.g. ACN-Data sessionID). |
| `arrival_idx`  | int   | First time step when charging is allowed (inclusive). |
| `departure_idx`| int   | First time step when charging is no longer allowed (exclusive). |
| `energy_kwh`   | float | Requested energy to deliver (kWh). |
| `charger_id`   | str   | Assigned charger/station (e.g. spaceID). |
| `max_power_kw` | float | Max charging power for this session (kW). |

Charging is allowed only for steps `t` in **[arrival_idx, departure_idx)**. Power must satisfy `0 ≤ p_i(t) ≤ max_power_kw`.

## DaySessions (one day)

- **`sessions`**: list of `Session` (order is fixed for schedule matrices).
- **`n_steps`**: number of time steps in the horizon.
- **`dt_hours`**: duration of each step (hours).

Every session must have `departure_idx ≤ n_steps`.

## Units

- Power: **kW**
- Energy: **kWh**

## Used by

Data loader, constraint checker, optimization solver, baseline, and agent pipeline.
