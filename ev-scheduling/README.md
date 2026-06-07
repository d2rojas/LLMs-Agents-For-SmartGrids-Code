# EV Charging Scheduling — EVAgent (§VI-B)

Allocate power to concurrent charging sessions so each vehicle gets its requested
energy before departure, under per-session and site-level caps. The optimization is
a linear program solved by **CVXPY**; the agent's job is to call it and report
faithfully.

## Problem
Day = 96 steps of 15 min. Per session i: arrival `a_i`, departure `d_i`, requested
energy `E_i^req`, power cap `p̄_i`; site cap `P̄_t`; TOU price `c_t`. Minimize TOU cost
+ penalty `λ·Σu_i` (slack `u_i` = unmet energy), s.t. availability, power, site-cap,
and energy-balance constraints. `Δt = 0.25 h`, `λ = 1e6 $/kWh` (globally optimal LP).

## Methods (identical session data, same checker)
1. **Numerical solver** — CVXPY called directly on structured data (gold standard).
2. **LLM-only** — GPT-4o or Claude Sonnet 4.6 outputs the schedule matrix directly,
   no optimizer/tools.
3. **EVAgent** — GPT-4o / Sonnet 4.6 backbone with a CVXPY tool, in a Parse → Optimize
   (`solve_ev_schedule`) → Explain loop. Every reported number traces to the tool JSON.

## Data
- **Caltech ACN-Data**, JPL site, 20 benchmark days. TOU: $0.12/kWh off-peak,
  $0.45/kWh peak (steps 64–83). `TODO(authors): ACN-Data access + day list`.

## Metrics (Table in §VI-B; mean ± std over 5 runs × 20 days, temp 0.7)
Cost ($), Peak (kW, 50 kW hard cap), Unmet (kWh), Served (%), Checker flags
(hard violations + energy-shortfall flags).

## Run
```bash
# TODO(authors), e.g.
# python run_ev.py --backend gpt-4o --mode evagent --days acn_jpl_20 --runs 5
```

## Verification
Shared constraint checker: hard-constraint violations on the availability/power/site-cap
constraints + energy-shortfall flags (`u_i > 0`).

## Files (to be added)
- `TODO(authors)`: `solve_ev_schedule` CVXPY tool, NL parser, agent loop, checker,
  ACN-Data loader, evaluation harness.
