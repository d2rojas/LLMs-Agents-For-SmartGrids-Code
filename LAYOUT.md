# One layout for every case study

Each case study is a separate project with its own dependencies, but they are read side by side,
and a reader who has understood one should be able to open another and know where everything is.
So the four folders follow one layout. It is the one `power-flow-agent/` arrived at first; the
others are being brought to it.

```
<case-study>/
  README.md              what the case study is, how to run it, where things are
  run.py                 the one entry point: run, postprocess, index, list-methods, show-prompt
  config.py | config/    site constants, model resolution, tolerances
  pricing.json           what a token costs, per model, for the cost estimate before a run
  requirements.txt       pinned; the case study runs in its own environment
  methods/               one folder per method: method.json and its .txt prompt texts
    _shared/             texts several methods share
    agent/               the multi-step agents and the verification gate (code)
    prompting/           the no-tools prompting strategies (code)
    deterministic/       the parser with no language model (code)
  solver/                the trusted tool, its schemas and its validators
  evaluation/            requests (the scenario generator), scoring, the runner, rescore,
                         postprocess, report, and page_fragments (the site)
  data/                  frozen inputs with a manifest of content hashes; no network at run time
  results/               <instance>/<date>/<model>/<method>/, see below; INDEX.md and INDEX.json
  tests/                 API-key-free; pins the prompt hashes
  ui/                    the interactive demo, when there is one
  viz/                   figures
```

## The rules the layout enforces

- **The six methods, with the same names and in the same order, everywhere:** `rule_based`,
  `llm_only_structured`, `llm_only_cot`, `plan_act_nogate`, `react_nogate`, and the case study's
  solver-grounded agent (`pfagent`, `evagent`, ...). A method that exists in one case study and not
  in another cannot be compared, so the set does not vary. `methods/README.md` is the table.
- **Every prompt is a `.txt` under `methods/`,** read by the code at import, its hash pinned by a
  test. A wording change fails the test until the pin is updated on purpose.
- **Every run leaves the same artefacts** in `results/<instance>/<date>/<model>/<method>/`:
  `REPORT.md` (written from the rows, never by a model), `summary.csv` (one line per request),
  `config.json` (the exact command, commit, prompt hash), `traces/` (every message sent and
  received), and `raw/` (the runner's own outputs). `run.py index` rebuilds `INDEX.md`.
- **Inputs are frozen and hashed** under `data/`. A run reads the copy in the repository; a file
  edited after freezing fails its hash check on load.
- **The site reads the code.** `evaluation/page_fragments.py` writes the case study's sections
  from the method registry, the gate's condition table, the scenario generator, the prompt
  builders and the result files, and `visuals/build.py` at the repository root assembles the four
  into one site with the same sections on every page. Nothing on the site is typed by hand.

## Where each case study stands

| case study | folder | layout | notes |
|---|---|---|---|
| Wind (6.1) | `wind-forecasting/` | done (2026-09-27) | the six methods on twenty frozen SDWPF windows, history only (no future inputs), the GRU as the trusted forecaster, gate W1–W5; the original scripts kept under `_legacy/` |
| EVAgent (6.2) | `ev-scheduling/` | in progress | `methods/` done; the rest of the moves in this branch |
| PFAgent (6.3) | `power-flow-agent/` | reference | `results/` layout, `run.py`, `methods/` as described |
| GridDebug (6.4) | `griddebug-agent/` | done (2026-09-27) | `run.py`, `methods/` (six), `solver/`, `evaluation/` with the frozen scenario manifest and `page_fragments.py`; the original FastAPI/Next.js demo kept under `ui/`, not wired to the six methods |
