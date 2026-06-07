# GridDebugAgent — Contingency Diagnosis (§VI-D)

A solver-grounded **ReAct** agent that iteratively diagnoses grid failures
(non-convergence, voltage violations outside 0.95–1.05 p.u., thermal overloads
>100% loading) and executes remediation on **PandaPower** networks via a
diagnose → act → verify loop.

## Components
1. **Preprocessing** — evidence collector + rule engine (extract metrics, classify failures).
2. **ReAct core** — GPT-4o (temp 0.3, ≤50 iterations) with OpenAI function calling.
3. **Tool suite (5 categories)** — query, simulation, diagnostic, grid actions
   (generation adjust, load curtailment, line/shunt switching, voltage control),
   memory management (snapshots, conversation logging).

The **LLM-only baseline** gets the same repair action primitives but no trusted tools,
simulation, or memory; it calls `propose_repair_action` once, which is validated,
applied to PandaPower, and evaluated with a single power-flow run.

## Data / protocol
39 scenarios across IEEE 14/30/57 (13 preset scenarios each: 4 non-convergence,
3 voltage, 3 thermal, 2 contingency, 1 normal base case).

## Metrics (Table in §VI-D)
Repair rate (converged, zero violations), Improve rate (converged, fewer violations),
Feasibility (converged), initial→final violation count. Also reported in text:
avg ReAct iterations, avg tool calls, avg latency.

## Run
```bash
# TODO(authors), e.g.
# python run_griddebug.py --network ieee57 --mode agent       # GridDebugAgent
# python run_griddebug.py --network ieee57 --mode llm_only     # baseline
```

## Verification
PandaPower convergence + voltage/thermal limit checks gate each repair step; all
reported numbers come only from PandaPower output.

## Files (to be added)
- `TODO(authors)`: ReAct agent, tool suite, rule engine, scenario generator,
  ModificationTools, evaluation harness.
