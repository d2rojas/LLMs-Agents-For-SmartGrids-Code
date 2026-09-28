# Wind power forecasting: the next 48 hours of one turbine from its history alone

A wind turbine's SCADA history for the last fourteen days is given; the next 3, 6 or 48 hours of
its active power have to be written down, 10-minute step by 10-minute step. Nothing after the last
history day is known to anyone. This case study measures six ways of doing that, from a parser
with the conventional forecaster to the solver-grounded agent, on twenty frozen instances of the
SDWPF farm (KDD Cup 2022), with one scorer for all six.

It follows the layout every case study in this repository follows; see [`../LAYOUT.md`](../LAYOUT.md).
The code of the original study, whose numbers the submitted paper carried, is kept unchanged under
[`_legacy/`](_legacy/) and is not part of the evaluation.

## Where things are

| path | what |
|---|---|
| `run.py` | the one entry point: `list-methods`, `show-prompt`, `freeze-data`, `train-gru`, `run`, `postprocess`, `rescore`, `index`, `serve` |
| `config.py` | the task (sampling, 14-day history, horizons, physical range, the KDD Cup abnormal-data rules, the train/test split), budgets (8 model calls, 12 tool calls, 600 s per request), model resolution |
| `methods/` | one folder per method with its `method.json` and `.txt` prompts; code by role under `methods/agent/`, `methods/prompting/`, `methods/deterministic/`; `methods/README.md` is the table |
| `solver/` | the trusted tools: `data.py` (the frozen windows, the abnormal rules, the hash check), `forecasters.py` (persistence, power curve, GRU), `gru.py` (the conventional forecaster, trained once), `tools.py` (the catalogue and the dispatcher) |
| `evaluation/` | `requests.py` (the request text and the question), `scoring.py` (one scorer), `runner.py`, `postprocess.py`, `rescore.py`, `page_fragments.py` (this case study's sections of the shared site) |
| `data/benchmark/` | the frozen instances: five turbines x four windows, sixteen days each, and `manifest.json` with a content hash per file and the choice rule |
| `data/gru/` | the GRU's training slices (days 1 to 214 of the five turbines) and its weights `gru_v1.json` with the training log |
| `results/` | `sdwpf/<date>/<model>/<method>/` with `REPORT.md`, `summary.csv`, `config.json`, `traces/` and `raw/`; see `results/README.md` |
| `tests/` | API-key-free: every method end to end with a scripted model, the gate, the scorer, the manifest, the prompt hashes |

## The six methods

The same six, with the same names and in the same order, as every other case study.

| method | LLM | tools | gate |
|---|---|---|---|
| `rule_based` — a regex parser reads the request, the GRU tool writes the series | no | yes | none |
| `llm_only_structured` — the model reads the history as CSV and writes the series itself | yes | no | none |
| `llm_only_cot` — the same plus one reasoning section | yes | no | none |
| `plan_act_nogate` — one call plans every tool call, executed without feedback | yes | yes | none |
| `react_nogate` — tool call, observation, repeat, inside the budget | yes | yes | none |
| `windagent` — the ReAct loop plus the verification gate W1–W5 | yes | yes | final |

`python run.py list-methods` prints this from `methods/`.

## What is different from the submitted paper's experiment

The submitted Section 6.1 fed the model ERA5 reanalysis wind for the very hours it was asked to
forecast (future information), on one turbine, one window and one call per cell, with a GRU row
taken from a student report. Here no method sees anything after the last history day, the
instances are twenty windows in the KDD Cup test period drawn by a fixed rule, the GRU is trained
in the repository on the training period only and receives the same inputs as every other row,
the abnormal-data rules of the KDD Cup decide which target points are scored, and every run
leaves its traces. The dataset's location and calendar dates are not published, so no weather
forecast of any kind is attached; that is stated in the manifest.

## Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # OPENROUTER_API_KEY (or OPENAI_API_KEY); the repo's power-flow-agent/.env is read too
```

The benchmark is frozen in `data/benchmark/` and needs no download. To rebuild it from the raw
SDWPF file (`wtbdata_245days.csv`, Zhou et al. 2024):

```bash
python run.py freeze-data --source /path/to/wtbdata_245days.csv    # refuses to overwrite without --force
python run.py train-gru --force                                     # about two minutes on a laptop CPU
```

A run refuses to start on an instance whose file hashes differently from the manifest.

## Running

```bash
python run.py run --dry-run                                                        # the cost estimate; spends nothing
python run.py run --method windagent --n 3 --horizon 48 --tag smoke --model openrouter:openai/gpt-4o-mini
python run.py run                                                                  # every method, every instance, every horizon
python run.py run --condition stress                                               # the last history day blanked: the correct answer is to escalate
python run.py index                                                                # results/INDEX.md
```

Every method sees the same requests, the same budget and the same answer contract. A request
that fails is written as a row with its error rather than omitted, and a request whose trace
exists already is kept unless `--force`. Nothing spends API credit without an explicit go, and
every run ends with `REPORT.md`.

## Tests

```bash
pytest
```

`tests/test_methods_end_to_end.py` runs all six methods on one request with a scripted model: a
series copied from a tool is solved, an invented one is wrong-unflagged without the gate and
escalated with it. `tests/test_methods_prompts.py` pins the hash of every prompt text under `methods/`.

## The shared site

```bash
cd .. && python -m visuals.build --case wind && open site/wind.html      # or: python run.py serve
```

`evaluation/page_fragments.py` writes this case study's sections from the method registry, the
gate's condition table, the frozen manifest, the prompt builders and the result files.
