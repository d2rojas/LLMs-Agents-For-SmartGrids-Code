# GridDebugAgent: diagnose and repair a faulted IEEE network

A power flow on an IEEE test network has failed or produced limit violations: a line is out, loads
have grown, a generator is gone, a setpoint is wrong. The task is to say what happened and to bring
the network back to a secure operating point with the actions a control room has, verified by the
power flow. This case study measures six ways of doing that, from a rule engine with no language
model to the solver-grounded agent, on twenty frozen fault instances per network, drawn from
thirteen fault classes, across the IEEE 14, 30, 57, 118 and 300-bus systems, with one scorer for
all six. Twenty instances on five networks is a hundred questions per method.

It follows the layout every case study in this repository follows; see [`../LAYOUT.md`](../LAYOUT.md).

## Where things are

| path | what |
|---|---|
| `run.py` | the one entry point: `list-methods`, `show-prompt`, `freeze-scenarios`, `run`, `postprocess`, `rescore`, `index`, `pages`, `serve` |
| `config.py` | limits (0.95–1.05 p.u., 100 %), budgets (20 model calls, 40 tool calls, 600 s per scenario), model resolution |
| `methods/` | one folder per method with its `method.json` and `.txt` prompts; code by role under `methods/agent/`, `methods/prompting/`, `methods/deterministic/`; `methods/README.md` is the table |
| `solver/` | the trusted tool: `network.py` (load, ratings, hash), `violations.py` (observe a network relative to its base), `evidence.py`, `rules.py`, `tools.py` (the catalogue and the dispatcher) and the tool bodies |
| `evaluation/` | `scenarios/` (the thirteen generators and their variants, `manifest.py`), `requests.py` (request text and evidence block), `scoring.py` (one scorer), `runner.py`, `postprocess.py`, `rescore.py`, `page_fragments.py` (this case study's sections of the shared site) |
| `data/scenarios/manifest.json` | the frozen scenario set: a content hash of each of the hundred injected networks, its initial state, the injected fault |
| `results/` | `<instance>/<date>/<model>/<method>/` with `REPORT.md`, `summary.csv`, `config.json`, `traces/` and `raw/`; see `results/README.md` |
| `tests/` | API-key-free: every method end to end with a scripted model, the gate, the answer contract, the manifest, the prompt hashes |
| `ui/` | the FastAPI and Next.js demo of the original project; not wired to the six methods and not part of the evaluation |

## The six methods

The same six, with the same names and in the same order, as every other case study.

| method | LLM | tools | gate |
|---|---|---|---|
| `rule_based` — the rule engine classifies, a fixed policy acts, the power flow verifies | no | yes | none |
| `llm_only_structured` — the model writes the actions as text; the harness applies them once | yes | no | none |
| `llm_only_cot` — the same plus one reasoning section | yes | no | none |
| `plan_act_nogate` — one call plans every tool call, executed without feedback | yes | yes | none |
| `react_nogate` — tool call, observation, repeat, inside the budget | yes | yes | none |
| `griddebug` — the ReAct loop plus the verification gate G1–G7 | yes | yes | final |

`python run.py list-methods` prints this from `methods/`.

## Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # OPENROUTER_API_KEY (or OPENAI_API_KEY); the repo's power-flow-agent/.env is read too
```

The networks come from `pandapower.networks`; line ratings are assigned by the rule of the
power-flow case study (1.25 times the base-case current). The scenario set is frozen in
`data/scenarios/manifest.json`, and a run refuses to start on an instance whose injected network
hashes differently from the manifest.

## Running

```bash
python run.py run --dry-run                                                  # the cost estimate; spends nothing
python run.py run --method griddebug --network case14 --model openrouter:openai/gpt-4o-mini
python run.py run                                                            # every method, every network, every scenario
python run.py index                                                          # results/INDEX.md
```

Every method sees the same scenarios, the same request, the same evidence block, the same budget
and the same answer contract. A scenario that fails is written as a row with its error rather than
omitted, and a scenario whose trace exists already is kept unless `--force`. Nothing spends API
credit without an explicit go, and every run ends with `REPORT.md`.

## Tests

```bash
pytest
```

`tests/test_methods_end_to_end.py` runs all six methods on one scenario with a scripted model:
a true repair is solved, a false claim is wrong-unflagged without the gate and escalated with it.
`tests/test_methods_prompts.py` pins the hash of every prompt text under `methods/`.

## The shared site

```bash
cd .. && python -m visuals.build --case griddebug && open site/griddebug.html      # or: python run.py serve
```

`evaluation/page_fragments.py` writes this case study's sections from the method registry, the
gate's condition table, the frozen manifest, the prompt builders and the result files. It feeds both
the shared site and the standalone pages under `results/visuals/`, which `run.py pages` writes and
`run.py serve` serves.
