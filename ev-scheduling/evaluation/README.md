# Evaluation

Implemented in `metrics/` (Phase A). Used by Phase A script and will be used by baseline/agent evaluation.

## Metrics (`evaluation/metrics/`)

- **`total_cost(schedule, tou, dt_hours)`**: Total energy cost ($) = ∑_t c(t)·(∑_i p_i(t))·dt.
- **`total_unmet_kwh(schedule, day, dt_hours)`**: Sum over sessions of max(0, E_i − delivered_i).
- **`peak_load_kw(schedule)`**: max_t ∑_i p_i(t).
- **`pct_fully_served(schedule, day, dt_hours)`**: % of sessions with delivered ≥ requested (0–100).
- **`charge_asap_schedule(day, site_p_max)`**: Uncontrolled baseline (max rate from arrival until E_i met); used for % cost reduction.
- **`compute_metrics(...)`**: Returns `Metrics` (cost, unmet, peak, violation_count, pct_fully_served, optional cost_reduction_vs_uncontrolled_pct).

## Planned

- **Faithfulness**: Verify numeric claims in explanations match computed schedule.
- **Stretch**: Sweep λ; cost–peak tradeoff. Compare baseline vs agent over 5+ days.
