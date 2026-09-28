# EVAgent: day-ahead EV charging from a request in plain language

A site operator describes a day of charging in plain language: the cars, when each one arrives and
leaves, how much energy it needs, what its charger can deliver. The task is to turn that into the
parameters of an optimization problem, solve it under the site's power cap and its time-of-use
tariff, and answer what was asked. This case study measures six ways of doing that, from a parser
with no language model to the solver-grounded agent, on twenty days of real charging sessions from
the ACN-Data portal, with one scorer for all six.

It follows the layout every case study in this repository follows; see [`../LAYOUT.md`](../LAYOUT.md).

## Where things are

| path | what |
|---|---|
| `run.py` | the one entry point: `list-methods`, `show-prompt`, `run`, `report`, `rescore`, `freeze-days`, `index`, `serve` |
| `methods/` | one folder per method with its `method.json` and its `.txt` prompts; the code by role under `methods/agent/`, `methods/prompting/`, `methods/deterministic/`. `methods/README.md` is the table |
| `solver/` | the trusted tool: the CVXPY linear program (`solver.py`) and the constraint checker (`checker.py`) |
| `evaluation/` | `requests.py` (the scenario generator), `stress.py` (the unanswerable days), `outcome.py` (solved / escalated / wrong-unflagged), `formulation.py`, `traceability.py`, `metrics/`, `runner.py` (the benchmark matrix), `rescore.py`, `report.py`, `page_fragments.py` (this case study's sections of the shared site) |
| `data/` | the session schema, the loader, and `data/benchmark/` with the twenty frozen days and their manifest of content hashes |
| `config/` | site constants and tariff (`site.py`), model resolution and the client (`llm.py`) |
| `results/` | `<instance>/<date>/<model>/<method>/` with `REPORT.md`, `summary.csv`, `config.json`, `traces/` and `raw/`; `INDEX.md` lists every method folder. See `results/README.md` |
| `tests/` | API-key-free; `test_methods_prompts.py` pins the hash of every prompt text |
| `ui/` | the FastAPI chat demo |
| `viz/` | schedule and load-profile plots |

## The six methods

The same six, with the same names and in the same order, as every other case study.

| method | LLM | tools | gate | runs today |
|---|---|---|---|---|
| `rule_based` — regular expressions read the request, the LP does the rest | no | yes | none | not yet |
| `llm_only_structured` — the model writes the kW matrix as text | yes | no | none | yes |
| `llm_only_cot` — the same plus one reasoning section | yes | no | none | yes |
| `plan_act_nogate` — one call emits the whole tool plan, then it executes | yes | yes | none | not yet |
| `react_nogate` — tool call, observation, repeat, inside the round budget | yes | yes | none | not yet |
| `evagent` — the ReAct loop plus the verification gate E1–E7 | yes | yes | final | yes |

`python run.py list-methods` prints this from `methods/`. The cost gap of every row is measured
against the CVXPY optimum of the same day, computed per request by the scorer; it is not a row.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # OPENROUTER_API_KEY for runs; ACN_DATA_API_TOKEN only to freeze new days
```

The twenty benchmark days are frozen under `data/benchmark/` and committed, so the benchmark
reproduces with no token and no network. Each day file carries its fetch timestamp and a sha256 of
its records; a day edited after freezing fails its hash check when it loads.

## Running

```bash
python run.py run --dry-run --days 20 --data-source cache     # the cost estimate; spends nothing
python run.py run --days 20 --data-source cache               # every method, every frozen day
python run.py report results/<dir> --pdf                      # REPORT.md next to the rows; no model is called
python run.py index                                           # results/INDEX.md
```

Every method sees the same days, the same generated requests (one list, hashed, the digest on every
row), the same seeds and the same completion budget. A run refuses to start if a method it was
asked for cannot run, writes a day that fails as a row with its error rather than omitting it, and
refuses to write a synthetic smoke test inside the repository.

Nothing spends API credit without an explicit go, and every run ends with `report`.

## Tests

```bash
pytest
```

`tests/test_methods_prompts.py` pins the sha256 of every prompt text under `methods/`. Changing a
prompt fails that test until the pin is updated on purpose, because a silent wording change would
make new runs incomparable with the ones already reported.

## The shared site

```bash
cd .. && python -m visuals.build && open site/index.html      # or: python run.py serve
```

`evaluation/page_fragments.py` writes this case study's sections from the method registry, the
gate's condition table, the scenario generator, the prompt builders and the result files. Nothing on
the site is typed by hand.
