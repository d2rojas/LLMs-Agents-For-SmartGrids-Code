# Agentic EV Charging Schedule Assistant

This project builds a day-ahead EV charging scheduler for a shared parking facility and compares three approaches: a direct-prompt LLM baseline, a CVXPY optimizer, and a full agentic pipeline (Plan → Optimize → Validate → Refine → Explain). We use real session data from [Caltech ACN-Data](https://ev.caltech.edu), minimize time-of-use energy cost under per-charger and site capacity constraints, and evaluate explanation faithfulness. There's also a FastAPI web GUI for interactive natural-language scheduling.

## Layout

| Path | Purpose |
|------|---------|
| `agent/` | Agentic pipeline: Plan → Optimize → Validate → Refine → Explain |
| `baseline/` | Direct LLM prompting baseline |
| `config/` | Site constraints, TOU rates, experiment configs |
| `constraints/` | Constraint checker (availability, per-charger, site cap, energy) |
| `data/` | ACN-Data loader, standardized session format, frozen benchmark days, synthetic fixtures |
| `evaluation/` | Metrics, benchmark runner, faithfulness evaluation |
| `optimization/` | CVXPY cost-minimization formulation and solver |
| `scripts/` | CLI entry points for all pipelines and benchmarks |
| `tests/` | Unit and integration tests |
| `visualization/` | Schedule and load-profile plots |
| `web/` | FastAPI server and HTML chat UI |
| `experiments/` | Benchmark outputs (CSV, JSON, plots) — gitignored |
| `results/` | Pre-computed reference results (the numbers reported in the paper, §VI-B) |
| `docs/` | Architecture and module reference (`ARCHITECTURE.md`) |

## Setup

### 1. Get the code

```bash
git clone <this-repo-url>
cd ev-scheduling
```

The Caltech `acnportal` library is installed automatically from PyPI by
`requirements.txt` in the next step — no separate clone is needed.

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

(`uv` also works: `uv venv && uv pip install -r requirements.txt`)

### 3. Set up API keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```
ACN_DATA_API_TOKEN=your_caltech_acn_token # from https://ev.caltech.edu
OPENAI_API_KEY=your_openai_key
```

`ACN_DATA_API_TOKEN` is needed for any script that fetches live session data. `OPENAI_API_KEY` is needed for the baseline, agent, and web GUI. Neither is committed — `.env` is gitignored.

## Session data

Sessions come from three places, in this order of preference.

| Source | Where it lives | When it is used |
|--------|----------------|-----------------|
| Frozen benchmark days | `data/benchmark/<site>_<date>.json` | Always, when the day is committed. No token, no network |
| ACN-Data API | https://ev.caltech.edu | Only when the day is not frozen and `ACN_DATA_API_TOKEN` is set |
| Synthetic fixtures | `data/benchmark/fixtures/SYNTHETIC_<site>_<date>.json` | Only when asked for explicitly |

`load_sessions(site_id, day_date, ...)` resolves this automatically. A caller selects the
source with the `source` argument (`"auto"`, `"cache"`, `"api"`, `"fixture"`) or, for scripts
that do not pass it, with the `EV_SESSIONS_SOURCE` environment variable:

```bash
python -m scripts.run_agent --site caltech --date 2019-06-15                     # frozen day, else API
EV_SESSIONS_SOURCE=fixture python -m scripts.run_agent_vs_baseline               # synthetic days, offline
EV_SESSIONS_SOURCE=cache python -m scripts.run_agent_vs_baseline                 # frozen days only, never the network
```

### Freezing the benchmark days

The 20 evaluation days behind the paper's §VI-B table are frozen once and then committed, so
the benchmark reproduces without a token. With `ACN_DATA_API_TOKEN` in `.env`, from the project
root:

```bash
python -m scripts.freeze_benchmark_days --dry-run   # list the days, fetch nothing
python -m scripts.freeze_benchmark_days             # fetch and write the missing days
```

Each day file holds the raw API records for that day, the fetch timestamp, the record count,
and a sha256 of the records. `data/benchmark/manifest.json` collects the same per day. Existing
files are never overwritten without `--force`, and a day file edited after freezing fails its
hash check on the next load.

### Synthetic fixtures

`data/benchmark/fixtures/` holds 20 generated days, one standing in for each benchmark date, so
the optimizer, constraint checker, baseline, agent, and tests can run before a token is
available. They are **not measurements**: the file name starts with `SYNTHETIC_`, the document
carries `synthetic: true` and a warning, every session and charger ID starts with `SYNTH-`, and
every fixture load prints a warning to stderr. Never report a number computed from them. Four of
the days request more energy than a 50 kW cap can deliver, so they exercise the unmet-energy and
infeasibility paths. Regenerate them (deterministically) with:

```bash
python -m data.benchmark.fixtures_gen --force
```

## LLM model

All LLM calls — the direct-prompt baseline, every agent stage, and the web GUI —
use OpenAI **`gpt-4o`** with `temperature=0.0` (deterministic decoding). The model
is set in `scripts/run_agent_vs_baseline.py` (`BASELINE_MODEL`) and as the default
of each entry point; the reference numbers in [`results/`](results/) (paper §VI-B)
were generated with this configuration.

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

`results/average_results_table.md` has the averaged benchmark metrics reported in
the paper (§VI-B): cost, peak load, unmet energy, % served, and constraint
violations for the optimizer, the LLM-only baseline, and the agent over the
20-day evaluation window. Re-run `scripts/run_agent_vs_baseline.py` to regenerate
the full outputs (per-day plots, day-by-day table, bar chart) under
`benchmark_results/`.

## Architecture

Module-level documentation (data schema, loader, solver formulation, constraint
checker, metrics) is consolidated in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
