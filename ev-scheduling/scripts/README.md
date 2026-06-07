# Scripts

## Phase A (implemented)

- **`run_phase_a`**: Load sessions from API (`--site`, `--date`), run optimizer, run constraint checker, compute metrics (cost, peak, unmet, % fully served, % cost reduction vs uncontrolled), print results and violations (if any), save schedule and load profile to `experiments/`.
  ```bash
  python -m scripts.run_phase_a --site caltech --date 2019-06-15
  ```
  Requires `ACN_DATA_API_TOKEN` in `.env`.

- **`run_baseline`**: Load sessions, run LLM baseline, check constraints, print metrics. Requires `OPENAI_API_KEY` in `.env`.
  ```bash
  python -m scripts.run_baseline --site caltech --date 2019-06-15
  ```

- **`run_agent`**: Load sessions, run agent pipeline (Plan → Optimize → Validate → Refine → Explain), check, metrics, plots. Requires `OPENAI_API_KEY` in `.env`.
  ```bash
  python -m scripts.run_agent --site caltech --date 2019-06-15
  ```

- **`run_benchmark_abc`**: Run Phase A, Phase B (baseline), and Phase C (agent) over multiple sites and 10–20 days; write `benchmark_results/metrics_abc.csv` and `metrics_abc.json`.
  ```bash
  python -m scripts.run_benchmark_abc
  python -m scripts.run_benchmark_abc --sites caltech jpl --ndays 15
  python -m scripts.run_benchmark_abc --sites caltech --dates 2019-06-15 2019-06-16 2019-06-17 --skip-c
  ```
  Options: `--sites`, `--ndays`, `--dates`, `--output-dir`, `--skip-b`, `--skip-c`.

- **`run_agent_vs_baseline`**: Compare Optimizer, LLM baseline, and Agent across 10–20 days. Both baseline and agent receive the same natural-language input per day (e.g., "I have 44 EVs: EV1 arrives 08:00 leaves 17:00 needs 12.5 kWh, ..."). Produces per-day schedule and load plots, day-by-day comparison table, and averaged results with bar chart.
  ```bash
  python -m scripts.run_agent_vs_baseline
  python -m scripts.run_agent_vs_baseline --ndays 10
  python -m scripts.run_agent_vs_baseline --skip-baseline
  ```
  Output: `benchmark_results/per_day/*.png`, `day_by_day_comparison.md`, `average_results_table.md`, `average_results_bar.png`. Options: `--ndays`, `--output-dir`, `--skip-optimizer`, `--skip-baseline`, `--skip-agent`, `--dates`.
