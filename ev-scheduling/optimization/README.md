# Optimization

Implemented in `solver.py` (CVXPY).

- **Decision variables**: `p[i,t]` (kW) per session per time step; `u[i]` (kWh) slack/unmet per session.
- **Objective**: min ∑_t c(t)·(∑_i p_i(t))·∆ + M·∑_i u_i; report peak = max_t ∑_i p_i(t).
- **Constraints**: Availability (p=0 outside [arrival, departure)), per-charger (p ≤ max_power_kw), site cap (∑_i p_i(t) ≤ P_max(t)), energy (delivered + u_i = E_i).

## API

- **`solve(day, site, tou, penalty_unmet=1e6)`** → `SolveResult` with `schedule`, `total_cost_usd`, `unmet_energy_kwh`, `peak_load_kw`, `success`, `message`.

Called by Phase A script and by the agent Optimize step. Stretch: add λ·peak to objective for cost–peak tradeoff.
