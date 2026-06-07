# Midway Meeting — ECE 285 EV Charging Schedule Assistant

**Group #10**: Ryan Luo, Peter Quawas  
**Use this as speaker notes / slide content.**

---

## Slide 1: Title

**Agentic EV Charging Schedule Assistant**

- Day-ahead scheduling for a parking facility
- **Goal**: Minimize TOU energy cost while meeting EV charging demand
- **Data**: Caltech ACN-Data (real sessions)
- **Compare**: Classical optimizer vs LLM baseline vs agentic pipeline

---

## Slide 2: Problem & Setup

**Inputs**
- Sessions per day: arrival/departure, requested energy (kWh), max power per charger
- Site: power cap (e.g. 50 kW), 96 time steps (15-min)
- TOU: off-peak $0.12/kWh, peak (4–9pm) $0.45/kWh

**Outputs**
- Schedule: power p[i,t] (kW) per session per time step
- Metrics: total cost ($), peak load (kW), unmet energy (kWh), % sessions fully served, % cost reduction vs “charge-asap”

**Constraints**
- Availability windows, per-charger limits, site cap, energy balance

---

## Slide 3: What We Built (Phase A — Done)

- **Data**: Loader for ACN-Data API → standardized `Session` / `DaySessions` (96 steps, 0.25 h)
- **Config**: `SiteConfig`, `TOUConfig`, default TOU rates
- **Checker**: Availability, per-charger, site cap, energy → violations + feasibility
- **Solver**: CVXPY — min cost + penalty for unmet; returns schedule, cost, peak, unmet
- **Metrics & viz**: Cost, peak, unmet, % served, cost reduction vs uncontrolled; schedule heatmap + load profile
- **Script**: `run_phase_a --site caltech --date YYYY-MM-DD` → plots in `experiments/`

---

## Slide 4: What We Built (Phase B — Baseline)

- **Prompt**: Full problem description + session table + strict output format (“Session i: p0 p1 … p95”)
- **LLM**: Single-shot GPT-4o call (max_completion_tokens configurable)
- **Parse**: Extract schedule matrix from text; validate 96 values per session
- **Script**: `run_baseline` — same metrics as Phase A for comparison

---

## Slide 5: What We Built (Phase C — Agent)

- **Pipeline**: Plan → Optimize → Validate → Refine → Explain
- **Plan** (v1): Pass-through; objective = minimize cost
- **Optimize**: Calls same CVXPY solver as Phase A
- **Validate**: Same constraint checker
- **Refine** (v1): No-op on failure
- **Explain**: Template-based summary from schedule facts (cost, peak, unmet, % cost reduction)
- **Script**: `run_agent` — same config as Phase A/baseline; outputs explanation + plots

---

## Slide 6: Benchmark — 5 Days, 3 Pipelines

| Pipeline   | Cost (typical) | Peak (kW) | % Served | Cost reduction vs uncontrolled |
|-----------|-----------------|-----------|----------|---------------------------------|
| Phase A   | $76–146         | 27–50     | 86–98%   | 17–35%                          |
| Agent     | Same as Phase A | Same      | Same     | Same                            |
| Baseline  | $3–34           | 7–28      | **0–8%** | 75–97%*                         |

*Baseline “cost reduction” is misleading: low cost because most energy is **unmet** (schedule mostly zeros or wrong shape).

**Takeaway**: Optimizer/agent deliver **86–98% of requested energy** with **17–35% cost savings** vs charge-asap. Baseline fails to produce valid 96-step schedules.

---

## Slide 7: Results Snapshot (One Day)

**Example: 2019-05-01, 44 sessions**

|           | Phase A / Agent | Baseline (2048 tok) |
|-----------|------------------|----------------------|
| Cost      | $111.57          | $3.36                |
| Peak      | 50.0 kW          | 28.0 kW              |
| Unmet     | 2.59 kWh         | **452 kWh**          |
| % served  | **97.7%**        | 4.5%                 |
| Violations| 1 (numerical)    | 44                   |

Agent explanation (grounded): *“Total cost: $111.57. Peak load: 50.0 kW. Unmet energy: 2.59 kWh. Cost reduction vs uncontrolled: 25.6%.”*

---

## Slide 8: Challenges — Baseline Parse Failures

- **Symptom**: LLM often outputs **24 values per session** (hourly) instead of **96** (15-min), or truncates mid-schedule.
- **Cause**: Token limit + strong “24 hours” prior; 96×N numbers don’t fit or get compressed.
- **Effect**: Parser rejects wrong-length lines → most sessions zero → very low cost but **massive unmet energy** and many violations.
- **Tried**: Increasing `max_completion_tokens` (2048 → 6144) → more sessions parsed, but still off-by-one/few or truncation.
- **Implication**: Direct LLM schedule generation is **not reliable** at 96-step resolution; supports motivation for **agentic** approach (optimizer does the math, LLM explains).

---

## Slide 9: What’s New — Faithfulness Check (Skeleton)

- **Goal**: Ensure explanation only states facts that match computed metrics (no hallucination).
- **Implemented**: `evaluation/faithfulness` — compare explanation claims (cost, peak, unmet, %) to ground-truth `ScheduleFacts`.
- **Modes**: (1) Parse explanation text (regex for v1 template) → extract claimed numbers → compare. (2) Direct fact-vs-fact comparison.
- **Output**: `FaithfulnessResult` — faithful yes/no + per-claim match/mismatch.
- **Status**: Skeleton + tests in place; can be wired into `run_agent` and final report.

---

## Slide 10: Next Steps

1. **Final benchmark & report**: Formalize 5-day tables/figures in LaTeX; add reproducibility notes to README.
2. **Faithfulness**: Integrate check into agent run; report “all explanations faithful” or document any mismatches (e.g. when using an LLM for explanation later).
3. **Baseline**: Optionally try hourly resolution (24 steps) + upsampling to 96 for a fairer comparison, or document limitation clearly.
4. **Stretch** (if time): Peak-penalty sweep (λ in objective); what-if (charger outage / demand surge).

---

## Slide 11: Summary

- **Done**: Full pipeline — data, solver, checker, baseline, agent (Plan → Optimize → Validate → Refine → Explain), benchmark over 5 days, faithfulness skeleton.
- **Result**: Optimizer/agent achieve high % served and real cost savings; baseline fails on 96-step output (parse/token limits).
- **Next**: Final report, faithfulness integration, optional baseline fix or stretch goals.

---

## Optional: One-Slide Diagram

**Data flow (single slide)**

```
ACN-Data API → DaySessions → [ Phase A: solve() → schedule → check → metrics → plots ]
                           → [ Baseline: prompt → LLM → parse → check → metrics ]
                           → [ Agent: plan → optimize → validate → refine → explain → check → metrics → plots ]
```

Use 1–2 figures from `Midway_results/` (e.g. `phase_a_2019-06-15_schedule.png` and `phase_a_2019-06-15_load.png`) to show a concrete schedule and load profile.
