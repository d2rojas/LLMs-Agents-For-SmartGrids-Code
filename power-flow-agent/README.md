# Power Flow Agent — PFAgent (§VI-C)

A conversational agent that delegates AC power flow to **PandaPower's Newton–Raphson
solver**, while the LLM parses multi-step queries, sequences tools, tracks network
state across turns, and synthesizes operator-readable responses.

## Components
1. **Streamlit frontend** — user interaction, session state, undo/redo snapshots.
2. **Agentic layer** — multi-turn conversation engine + tool dispatcher (≤8 rounds,
   40-message history).
3. **Solver backend** — PandaPower AC power flow, N-1 contingency, remedial actions.
4. **Visualization** — topology, voltage heat maps, flow diagrams.

For evaluation, LLM-only and PFAgent see the same cases/metrics; only PFAgent can
call the PandaPower toolchain.

## Models
Claude Opus 4.7, GPT-5.4, GPT-5.5.

## Data / protocol
IEEE 14/30/57/118-bus (MATPOWER base). Loads and generator setpoints are randomly
perturbed around the base case to mitigate memorization; Table uses `k = 1`
(day-to-day variation) with `N = 40` seeds per system. Ground truth from PandaPower
Newton–Raphson on each perturbed case.

## Metrics (three tiers; Table reports one per tier)
- Tier I (state): `V_MAE` (p.u.), V-RMSE, angle RMSE, max V error.
- Tier II (flow): `F_MAE` (MW), F-RMSE, P95 flow error, branch-loading RMSE (%).
- Tier III (physical): bus-level active-power-balance / KCL residual `B_mean` (MW).

## Run
```bash
# Streamlit UI:        TODO(authors), e.g.  streamlit run app.py
# Batch evaluation:    TODO(authors), e.g.  python eval_pf.py --model gpt-5.4 --k 1 --seeds 40
```

## Verification
Newton–Raphson convergence + KCL self-consistency; schema-valid success rate.

## Files (to be added)
- `TODO(authors)`: Streamlit app, tool implementations (load_case, run_powerflow,
  check_voltage_violations, contingency, remedial actions), perturbation generator,
  evaluation harness, seeds.
