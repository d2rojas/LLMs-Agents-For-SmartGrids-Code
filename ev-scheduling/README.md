# ECE 285 — Agentic EV Charging Schedule Assistant

**Group 10**: Ryan Luo, Peter Quawas

This project builds a day-ahead EV charging scheduler for a shared parking facility and compares three approaches: a direct-prompt LLM baseline, a CVXPY optimizer, and a full agentic pipeline (Plan → Optimize → Validate → Refine → Explain). We use real session data from [Caltech ACN-Data](https://ev.caltech.edu), minimize time-of-use energy cost under per-charger and site capacity constraints, and evaluate explanation faithfulness. There's also a FastAPI web GUI for interactive natural-language scheduling.

## Layout

| Path | Purpose |
|------|---------|
| `agent/` | Agentic pipeline: Plan → Optimize → Validate → Refine → Explain |
| `baseline/` | Direct LLM prompting baseline |
| `config/` | Site constraints, TOU rates, experiment configs |
| `constraints/` | Constraint checker (availability, per-charger, site cap, energy) |
| `data/` | ACN-Data loader and standardized session format |
| `evaluation/` | Metrics, benchmark runner, faithfulness evaluation |
| `optimization/` | CVXPY cost-minimization formulation and solver |
| `scripts/` | CLI entry points for all pipelines and benchmarks |
| `tests/` | Unit and integration tests |
| `visualization/` | Schedule and load-profile plots |
| `web/` | FastAPI server and HTML chat UI |
| `experiments/` | Benchmark outputs (CSV, JSON, plots) — gitignored |
| `final_report_results/` | Pre-computed results used in the final report |
| `acnportal/` | ACN-Data/ACN-Sim client (cloned separately, see Setup) |

## Setup

### 1. Clone and install acnportal

```bash
git clone <this-repo-url>
cd Project
git clone https://github.com/zach401/acnportal acnportal
```

The `acnportal` library is not bundled in this repo and needs to be cloned separately.

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

(`uv` also works: `uv venv && uv pip install -r requirements.txt`)

### 3. Set up API keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```
ACN_DATA_API_TOKEN=your_caltech_acn_token   # from https://ev.caltech.edu
OPENAI_API_KEY=your_openai_key
```

`ACN_DATA_API_TOKEN` is needed for any script that fetches live session data. `OPENAI_API_KEY` is needed for the baseline, agent, and web GUI. Neither is committed — `.env` is gitignored.

## Tests

From the project root with the venv active:

```bash
pytest
```

To run a specific file:

```bash
pytest tests/test_constraints.py
pytest tests/test_baseline_parse.py
pytest tests/test_data_loader.py
pytest tests/test_faithfulness.py
```

- `test_constraints.py` — constraint checker: feasible schedule and one violation per constraint type
- `test_baseline_parse.py` — LLM output resampling and schedule parsing
- `test_data_loader.py` — ACN-Data API loader and session format conversion (skips live fetch if token not set)
- `test_faithfulness.py` — claim extraction and ground-truth comparison for explanation faithfulness

## Web GUI

Start the server from the project root:

```bash
uvicorn web.app:app --reload --port 8000
```

Then open http://localhost:8000.

You can type a natural-language scheduling request like:

> "I have 5 EVs. EV1 arrives at 08:00, leaves at 17:00, and needs 20 kWh. EV2 arrives at 09:00, leaves at 18:00, needs 15 kWh. Site capacity is 50 kW. Schedule for today."

The agent parses the request, solves the optimizer, validates constraints, and returns a plain-English explanation with a schedule table and load-profile chart. Follow-up questions like "what if EV3 arrives two hours later?" work within the same session.

Needs `OPENAI_API_KEY` in `.env`.

## Running the Pipelines

All commands below should be run from the project root with the venv active.

### Phase A — Optimizer only

```bash
python -m scripts.run_phase_a --site caltech --date 2019-06-15
```

Pulls sessions from the ACN-Data API, solves the CVXPY schedule, checks constraints, prints metrics (cost, peak load, unmet energy, % fully served, % cost reduction vs uncontrolled), and saves plots to `experiments/`. Needs `ACN_DATA_API_TOKEN`.

### Phase B — LLM Baseline

```bash
python -m scripts.run_baseline --site caltech --date 2019-06-15
```

Sends session data as a natural-language prompt and parses the LLM's returned schedule. Checks constraints and prints the same metrics. Needs `OPENAI_API_KEY`.

### Phase C — Agentic Pipeline

```bash
python -m scripts.run_agent --site caltech --date 2019-06-15
```

Runs the full Plan → Optimize → Validate → Refine → Explain pipeline, then checks constraints and saves plots. Needs `OPENAI_API_KEY`.

### Full Benchmark (A + B + C)

```bash
python -m scripts.run_benchmark_abc
python -m scripts.run_benchmark_abc --sites caltech jpl --ndays 15
python -m scripts.run_benchmark_abc --sites caltech --dates 2019-06-15 2019-06-16 --skip-c
```

Runs all three phases across multiple sites and days and writes results to `benchmark_results/metrics_abc.csv` and `metrics_abc.json`. Options: `--sites`, `--ndays`, `--dates`, `--output-dir`, `--skip-b`, `--skip-c`. Needs both keys.

### Agent vs Baseline Comparison

```bash
python -m scripts.run_agent_vs_baseline
python -m scripts.run_agent_vs_baseline --ndays 10
python -m scripts.run_agent_vs_baseline --skip-baseline
```

Runs the optimizer, baseline, and agent on the same natural-language input for each day and compares results. Outputs per-day plots to `benchmark_results/per_day/`, plus `day_by_day_comparison.md`, `average_results_table.md`, and `average_results_bar.png`. Options: `--ndays`, `--output-dir`, `--skip-optimizer`, `--skip-baseline`, `--skip-agent`, `--dates`. Needs `OPENAI_API_KEY`.

## Pre-computed Results

`final_report_results/` has the benchmark outputs we used in the report:

- `agent_vs_baseline_metrics.csv` — averaged metrics across all evaluation days
- `average_results_table.md` — summary table
- `average_results_bar.png` — bar chart comparing all three pipelines
- `phase_a_schedule.png`, `phase_a_load.png` — example Phase A outputs
- `agent_schedule.png`, `agent_load.png` — example agent outputs
- `per_day/` — per-day schedule and load plots for all three pipelines

## Report

Final report: `reports/final_report.tex` (PDF: `reports/i.pdf`).
