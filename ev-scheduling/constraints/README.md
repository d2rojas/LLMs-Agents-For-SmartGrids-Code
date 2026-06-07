# Constraint checker

Implemented in `checker.py`. Verifies a schedule (shape `n_sessions × n_steps`, power in kW) against sessions and site config.

## Constraints

- **Availability**: `p_i(t) = 0` for `t ∉ [a_i, d_i)`.
- **Per-charger limits**: `0 ≤ p_i(t) ≤ p̄_i`.
- **Site power cap**: `∑_i p_i(t) ≤ P_max(t)` at each `t`.
- **Energy**: Delivered = ∑_t p_i(t)·∆; no over-delivery; unmet = max(0, E_i − delivered).

## API

- **`check(schedule, day, site, dt_hours=None, tol=None)`** → `CheckResult` with `feasible`, `violations` (list of `Violation`: kind, session_id, time_step, message), `unmet_energy_kwh`, `peak_load_kw`.
- **`DEFAULT_TOL = 1e-5`**: Numerical tolerance; override with `tol` for stricter/looser checks.

Used by Phase A script, baseline (optional repair), and agent (Validate step).
