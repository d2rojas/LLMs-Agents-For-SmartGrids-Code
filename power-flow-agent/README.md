# Power Flow Agent (PFAgent)

A conversational agent that delegates AC power flow to **PandaPower's Newton–Raphson
solver**, while the LLM parses multi-step natural-language queries, sequences tools,
tracks network state across turns, and synthesizes operator-readable responses.
For evaluation, an LLM-only baseline and PFAgent see the same cases and metrics; only
PFAgent can call the PandaPower toolchain.

> The full implementation, architecture notes, and detailed instructions live in
> [`LLM/`](LLM/) — see **[`LLM/README.md`](LLM/README.md)**. This page is a summary.

## Components
1. **Streamlit frontend** — user interaction, session state, undo/redo snapshots.
2. **Agentic layer** — multi-turn conversation engine + tool dispatcher (≤8 rounds).
3. **Solver backend** — PandaPower AC power flow, N-1 contingency, remedial actions.
4. **Visualization** — topology, voltage heat maps, flow diagrams.

## Quick start
```bash
cd LLM
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Set API keys (only needed for the LLM chat / baseline, not for the solver):
export OPENAI_API_KEY=...        # GPT-5.4 / GPT-5.5
export GEMINI_API_KEY=...        # Gemini (optional)

# Interactive UI:
streamlit run app.py

# Batch evaluation (LLM-only vs PFAgent across IEEE cases):
python benchmarks/evaluate_llms.py
```

## Data / protocol
MATPOWER IEEE 14/30/57/118-bus cases (bundled in [`LLM/data/`](LLM/data/) and
`data/`). Loads and generator setpoints are perturbed around the base case to
mitigate memorization (`k = 1`, `N = 40` seeds per system). Ground truth is the
PandaPower Newton–Raphson solution of each perturbed case.

## Metrics (three tiers; the paper reports one per tier)
- **Tier I — state:** voltage-magnitude MAE (`V_MAE`, p.u.), V-RMSE, angle RMSE, max V error.
- **Tier II — flow:** branch active-power MAE (`F_MAE`, MW), F-RMSE, P95 flow error, branch-loading RMSE (%).
- **Tier III — physical:** bus-level active-power-balance / KCL residual (`B_mean`, MW).

Reproduces the power-flow results table in the paper (§VI-C).

## Verification
Newton–Raphson convergence + KCL self-consistency + schema-valid success rate gate
what is reported.

## Tests
```bash
cd LLM && pip install pytest && pytest        # solver/N-1/remedial tests run without API keys
```
