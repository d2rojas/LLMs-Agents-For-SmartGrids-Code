# methods/

One folder per evaluated method. Each folder has a `method.json` (what the method is, how the
runner names it, which prompt texts it uses) and the `.txt` prompt texts specific to it.
Texts several methods share live in `_shared/`.

These files are the **only** copy of every prompt. `agent/prompts.py`, `prompting/prompt_variants.py`,
`agent/engine.py` and `prompting/prompts_baseline.py` read them at import time, so editing a
`.txt` changes the prompt for the benchmark and the Streamlit app alike.
`tests/test_methods_prompts.py` pins the hash of every text to the value stamped on the runs
behind the paper tables. Changing a prompt therefore fails a test until the pin is updated on
purpose, which is the point: a silent wording change would make new runs incomparable with the
committed ones. Do not strip or reflow whitespace in these files.

| folder | runner name | what it is | tools | gate |
|---|---|---|---|---|
| `rule_based` | `rule_based` | Deterministic regex parser, no LLM. The conventional-workflow row. | yes | none |
| `llm_only_structured` | `llm_only:structured` | LLM answers from the case tables in the prompt. Structured prompt, JSON output. | no | none |
| `llm_only_cot` | `llm_only:cot` | Structured plus a step-by-step reasoning section. | no | none |
| `plan_act_nogate` | `plan_act_nogate` | One planning call emits the whole tool plan, then it executes. | yes | none |
| `react_nogate` | `react_nogate` | ReAct loop: thought, tool call, observation, up to 8 rounds. | yes | none |
| `pfagent` | `pfagent` | ReAct loop plus the task-level verification gate V1 to V7 on the final answer. The solver-grounded row. | yes | final gate |

These six are the current design (`run.py list-methods` shows them first, with the file and function that run each one; the map is also in `docs/ARCHITECTURE.md`). Every method receives
the same rules block (`_shared/common_rules.txt`), the same operations catalogue (`agent/tools.py`,
rendered with the argument enums for the no-tools methods) and the same answer contract
(`_shared/output_contract.txt`), and every method's answer is scored by the same evaluator
(`evaluation/common_eval.py`). Formulation is the ordered list of solver operations the method
declares in `formulation`, compared with the reference operations of the request; with tools it
must also match the operations actually executed.

`_archive/` keeps the variants that are not part of the design (few-shot, RAG, hand Newton-Raphson,
the forced and probe prompting rows, the single-call rows, the gated ReAct and Plan-and-Act, the
pre-verification PFAgent). They still load, run and rescore, so their old result folders keep
rendering, but they are marked `[archived]` in `run.py list-methods` and their prompts are not part
of the shared design.

## Reading a method

```bash
.venv/bin/python run.py list-methods
.venv/bin/python run.py show-prompt --method pfagent            # card + assembled system prompt + hash
.venv/bin/python run.py show-prompt --method plan_act_nogate --tool-variant load_split   # also the planner prompt
```

## What is in a prompt and what is not

The `.txt` files hold every fixed sentence. Three things are still built by code at run time,
because they depend on the request or on the network, and `method.json` names them under
`dynamic_parts`:

- the system-data block (case tables rendered from the seed-perturbed network, or the rows
  RAG retrieved for the request), built in `prompting/prompt_variants.py`;
- the operations catalogue (`agent/tools.py`, `--tool-variant v1|load_split`): the tool schemas
  passed to the API for the tool methods, the same catalogue rendered as text under `## Operations`
  for the no-tools methods, and the catalogue appended to
  `plan_act_nogate/plan_system_prompt_prefix.txt` for the planner;
- the two worked examples of the archived few-shot variants (`prompting/prompt_variants.py`).

## Adding a method

1. Create `methods/<name>/method.json` (copy a neighbour; `runner_name` must be a name
   `evaluation/runner.py --method` accepts, so a genuinely new architecture also needs
   an entry in `ARCH_METHODS` there or a new strategy in `prompting/prompt_variants.py`).
2. Put its fixed texts in `methods/<name>/*.txt` and list them in `prompt_files`.
3. Add the new texts to `PINNED_TEXTS` in `tests/test_methods_prompts.py` once the wording is
   final.
