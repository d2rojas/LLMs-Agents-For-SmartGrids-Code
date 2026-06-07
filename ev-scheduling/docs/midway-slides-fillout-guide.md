# Midway Slides — Fill-out Guide

Use this with your Contents: **Current Progress (Phase A, B, C)** → **Benchmark overview** → **One-day example** → **Challenges** → **Next steps**.

---

## 1. Current Progress — Phase A

**What to put on the slide**

- **Title**: Current Progress — Phase A
- **Bullets**:
  - **Data & format**: ACN-Data API → standardized sessions (96 steps, 15-min). `DaySessions` + `Session` in `data/format/schema.py`.
  - **Config**: Site cap 50 kW, TOU off-peak $0.12 / peak $0.45 per kWh (`config/site.py`).
  - **Constraint checker**: Availability, per-charger limit, site cap, energy balance → `CheckResult` (feasible, violations). `constraints/checker.py`.
  - **Optimizer**: CVXPY — minimize TOU cost + penalty for unmet energy. `optimization/solver.py`.
  - **Metrics & viz**: Cost, peak load, unmet (kWh), % fully served, % cost reduction vs charge-asap; schedule heatmap + load profile. `evaluation/metrics`, `visualization/plots.py`.
  - **Script**: `python -m scripts.run_phase_a --site caltech --date 2019-06-15` → prints metrics, writes `experiments/phase_a_schedule.png`, `phase_a_load.png`.

**How to generate/verify**

- Run:  
  `python -m scripts.run_phase_a --site caltech --date 2019-05-01`  
- You should see: ~44 sessions, cost ~$111.57, peak 50 kW, % served ~97.7%. Plots appear in `experiments/` if the folder exists.

---

## 2. Current Progress — Phase B

**What to put on the slide**

- **Title**: Current Progress — Phase B
- **Bullets**:
  - **Baseline**: Single-shot LLM (GPT-4o) asked to output a full schedule from problem description + session table.
  - **Prompt**: Objective, 96-step horizon, constraints, session table; output format “Session i: p0 p1 … p95” per session. `baseline/prompt.py`.
  - **Parse**: Extract schedule matrix from model text; require exactly 96 values per session. `baseline/parse.py`.
  - **Run**: `run_baseline(day, site, tou)` → schedule (or zeros on parse failure). `baseline/run.py`.
  - **Evaluation**: Same checker and metrics as Phase A. Script: `python -m scripts.run_baseline --site caltech --date 2019-05-01 --model gpt-4o`.
  - **Result**: Baseline often fails to produce valid 96-step schedules (parse errors, truncation) → low % served in benchmarks.

**How to generate/verify**

- Run:  
  `python -m scripts.run_baseline --site caltech --date 2019-05-01 --model gpt-4o`  
- You should see metrics and possibly “Parse failed” and low % fully served (e.g. ~4.5% for that date). Needs `OPENAI_API_KEY` in `.env`.

---

## 3. Current Progress — Phase C

**What to put on the slide**

- **Title**: Current Progress — Phase C
- **Bullets**:
  - **Agent pipeline**: Plan → Optimize → Validate → Refine → Explain. `agent/run.py`.
  - **Plan (v1)**: Pass-through; objective = “minimize cost”. `agent/plan/plan.py`.
  - **Optimize**: Calls same CVXPY solver as Phase A. `agent/optimize/call_solver.py`.
  - **Validate**: Same constraint checker. `agent/validate/validate.py`.
  - **Refine (v1)**: No-op on solver failure. `agent/refine/refine.py`.
  - **Explain**: Template-based summary from schedule facts (cost, peak, unmet, % cost reduction). `agent/explain/explain.py`.
  - **Script**: `python -m scripts.run_agent --site caltech --date 2019-05-01` → schedule, metrics, and a short explanation; plots in `experiments/agent_schedule.png`, `agent_load.png`.

**How to generate/verify**

- Run:  
  `python -m scripts.run_agent --site caltech --date 2019-05-01`  
- You should see the same cost/peak/unmet as Phase A and a line like:  
  *“Total cost: $111.57. Peak load: 50.0 kW. Unmet energy: 2.59 kWh. Cost reduction vs uncontrolled: 25.6%.”*

---

## 4. Benchmark overview

**What to put on the slide**

- **Title**: Benchmark overview
- **Content**:
  - **Setup**: 5 days (2019-05-01, 2019-05-15, 2019-06-03, 2019-06-15, 2018-11-05), Caltech site, same config for all three pipelines.
  - **Table** (from `Midway_results/metrics_summary.csv`):

| Pipeline  | Cost range   | Peak (kW) | % Served (range) | Cost reduction vs uncontrolled |
|-----------|--------------|-----------|-------------------|--------------------------------|
| Phase A   | $38–146      | 27–50     | 86–98%            | 17–35%                         |
| Agent     | Same as Phase A | Same   | Same              | Same                           |
| Baseline  | $3–34        | 7–28      | **0–8%**          | High % but due to unmet energy |

  - **Takeaway**: Phase A and Agent match; both achieve high % served and real cost savings. Baseline has very low % served and many violations because of parse/format issues.

**How to generate the data**

- From project root with venv active and `.env` set (ACN + OpenAI keys):  
  `python -m scripts.run_midway_results`  
- This runs Phase A, Agent, and Baseline for the 5 dates, writes:
  - `Midway_results/metrics_summary.csv`
  - `Midway_results/REPORT.md`
  - `Midway_results/*.png` (schedule and load plots per pipeline per date)
- Use the CSV for the table; you can open it in Excel/Sheets or paste the table from `Midway_results/REPORT.md`.

---

## 5. One-day example

**What to put on the slide**

- **Title**: One-day example (e.g. 2019-05-01, 44 sessions)
- **Content**:
  - **Metrics table** (one day, three pipelines):

|            | Phase A | Agent | Baseline |
|------------|---------|-------|----------|
| Cost       | $111.57 | $111.57 | $3.36  |
| Peak (kW)  | 50.0    | 50.0  | 28.0     |
| Unmet (kWh)| 2.59    | 2.59  | **452**  |
| % served   | **97.7%** | **97.7%** | 4.5%  |
| Violations | 1       | 1     | 44       |

  - **Agent explanation (grounded)**:  
    *“Total cost: $111.57. Peak load: 50.0 kW. Unmet energy: 2.59 kWh. Cost reduction vs uncontrolled: 25.6%.”*
  - **Optional**: One figure from `Midway_results/phase_a_2019-05-01_schedule.png` or `phase_a_2019-05-01_load.png` (or the same from `agent_*` — they match Phase A).

**How to generate/verify**

- The numbers come from `Midway_results/metrics_summary.csv` (rows for 2019-05-01).
- Explanation text: from `Midway_results/agent_2019-05-01_explanation.txt`, or run:  
  `python -m scripts.run_agent --site caltech --date 2019-05-01`  
  and copy the “Explanation:” line from the console.
- Figures: use existing PNGs in `Midway_results/` for that date (or regenerate with `run_midway_results`).

---

## 6. Challenges

**What to put on the slide**

- **Title**: Challenges
- **Bullets**:
  - **Baseline output format**: Model often outputs **24 values per session** (hourly) instead of **96** (15-min), or wrong length → parser rejects → most sessions zero → very low cost but **large unmet energy** and many violations.
  - **Token limit**: Full 96×N schedule is large; with 2048 tokens the model truncates or compresses; raising to 6144 helps only partly (still off-by-one or truncation around session 10–15).
  - **No free fix**: Making the baseline reliably output 96 steps would need either much larger token budget, or a different design (e.g. hourly baseline + upsampling to 96).
  - **Positive**: This motivates the **agentic** design: optimizer does the math; explanation stays grounded in solver output.

**How to generate/verify**

- Run baseline with different token limits and compare % served and parse errors, e.g.:  
  In `scripts/run_midway_results.py` set `max_completion_tokens=2048` (or 6144), run, then inspect `Midway_results/REPORT.md` and CSV. You’ll see baseline “Parse failed” messages and low % served.

---

## 7. Next steps

**What to put on the slide**

- **Title**: Next steps
- **Bullets**:
  - **Final report**: Put benchmark tables and one-day example into LaTeX (`reports/final_report.tex`); add 1–2 figures from `Midway_results/`.
  - **Faithfulness**: Wire `evaluation.faithfulness.check_faithfulness` into the agent run (or a small script); report that explanations are faithful to computed metrics (or document mismatches if you add LLM-based explanation later).
  - **Baseline** (optional): Try 24-step baseline + upsampling to 96 for a fairer comparison, or clearly document the 96-step limitation.
  - **Stretch** (if time): Peak-penalty sweep (λ in objective); what-if (e.g. charger outage, demand surge).

**How to generate data for the report**

- Re-run full benchmark:  
  `python -m scripts.run_midway_results`  
- Use `Midway_results/metrics_summary.csv` and `REPORT.md` for tables and narrative; use `Midway_results/*_schedule.png` and `*_load.png` for figures.

---

## Quick reference: Commands

| Goal                     | Command |
|--------------------------|--------|
| Phase A one day          | `python -m scripts.run_phase_a --site caltech --date 2019-05-01` |
| Baseline one day         | `python -m scripts.run_baseline --site caltech --date 2019-05-01 --model gpt-4o` |
| Agent one day            | `python -m scripts.run_agent --site caltech --date 2019-05-01` |
| Full 5-day benchmark     | `python -m scripts.run_midway_results` |
| Metrics table            | Open `Midway_results/metrics_summary.csv` or `Midway_results/REPORT.md` |
| Agent explanation (file) | `Midway_results/agent_<date>_explanation.txt` |

All from project root with venv active; Phase A and Agent need `ACN_DATA_API_TOKEN`; Baseline also needs `OPENAI_API_KEY` in `.env`.
