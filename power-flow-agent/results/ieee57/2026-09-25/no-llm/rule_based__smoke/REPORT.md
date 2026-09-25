# rule_based on IEEE 57-bus with no-llm

Generated 2026-09-25 14:17 by evaluation/postprocess.py from `report.rescored.json`. Runs: 3. Scored by the unified evaluator (v2): every verdict below is read from the answer JSON, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-25 |
| model | none:rule_based |
| method | rule_based |
| case | case57 |
| condition | normal |
| n | 3 |
| seed | 0 |
| k | 1 |
| max_rounds | 8 |
| tool_variant | load_split |
| plan_variant | text |
| temperature | 0.0 |
| system_prompt_hash | None |
| description | Deterministic regex parser maps the request to tool calls, no LLM (methods/deterministic/rule_based.py). The conventional-workflow row. |
| prompt files | none (no LLM) |

![overview of the runs](overview.png)

One row per request, one cell per step (blue LLM call, teal tool call, purple planner, gold verification; green or red edge is the gate verdict), then formulation and where the request ended. Each run also has its own figure next to its traces: `traces/NN_<request>.png`.

## Where every request ended

The three outcomes are exclusive and sum to the run count. Escalation takes precedence: a run the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 3 | 100.0% |
| Escalated to a person | 0 | 0.0% |
| Wrong, unflagged | 0 | 0.0% |
| **Total** | **3** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 3/3 (100.0%) |
| Task utility | Voltage MAE, all runs | 2.23e-07 p.u. |
| Task utility | Voltage MAE, formulation-exact runs | 2.23e-07 p.u. |
| Task utility | Flow MAE, all runs | 0.0528 MW |
| Task utility | Flow MAE, formulation-exact runs | 0.0528 MW |
| Task utility | KCL mismatch, mean | 1.33e-04 MW |
| Solver-grounded correctness | Solved (computation right, any path) | 3/3 (100.0%) |
| Solver-grounded correctness | V-pass (all conditions, offline) | 3/3 (100.0%) |
| Reporting | Traceable answers | 3/3 (100.0%) |
| Reporting | Traceable numbers, mean share | 1 |
| Reporting | Stale state quoted | 0/3 |
| Cost and time | LLM calls / tool calls, mean | 0 / 2.67 |
| Cost and time | Prompt / completion tokens, mean | 0 / 0 |
| Cost and time | Cost, total | $0.0000 |
| Cost and time | Wall time, mean | 0.2 s |

### Cross-check against the runner's own scoreboard

Values the runner aggregated for the same rows (report.json scoreboard). They should agree with the table above; a disagreement means the rows were filtered differently.

| metric | runner scoreboard | this report |
|---|---:|---:|
| common_solved_count | 3 | 3 |
| common_escalated_count | 0 | 0 |
| common_wrong_count | 0 | 0 |
| common_formulation_count | 3 | 3 |
| common_traceable_count | 3 | 3 |
| common_n | 3 | 3 |

## By request difficulty

| difficulty | n | solved | escalated | wrong unflagged | formulation exact |
|---|---:|---:|---:|---:|---:|
| ambiguous | 1 | 1 | 0 | 0 | 1 |
| multistep | 1 | 1 | 0 | 0 | 1 |
| parameterized | 1 | 1 | 0 | 0 | 1 |

## Files

- `summary.csv`: one line per run, the fields above plus tokens and time.
- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.
- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.
- `traces/NN_<request>.png`: the run as a picture: steps, gate verdicts, formulation, verification, outcome, with a two-line narrative.
- `overview.png`: all runs of this folder on one page.
- `traces/NN_<request>.json`: the raw trace the runner wrote.
- `raw/`: the runner's own outputs (report.json, rescored report, logs).
- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.
