# methods/

One folder per evaluated method. Each folder has a `method.json` (what the method is, how the
runner names it, which prompt texts it uses) and the `.txt` prompt texts specific to it.
Texts several methods share live in `_shared/`.

These files are the **only** copy of every prompt. `llm/prompts.py`, `llm/prompt_variants.py`,
`llm/engine.py` and `baselines/prompts_baseline.py` read them at import time, so editing a
`.txt` changes the prompt for the benchmark and the Streamlit app alike.
`tests/test_methods_prompts.py` pins the hash of every text to the value stamped on the runs
behind the paper tables. Changing a prompt therefore fails a test until the pin is updated on
purpose, which is the point: a silent wording change would make new runs incomparable with the
committed ones. Do not strip or reflow whitespace in these files.

| folder | runner name | what it is | tools | gate |
|---|---|---|---|---|
| `llm_only_structured` | `llm_only:structured` | LLM answers from the case tables in the prompt. Structured prompt, JSON output. | no | no |
| `llm_only_few_shot` | `llm_only:few_shot` | Structured plus two worked examples on a fictional system. | no | no |
| `llm_only_cot` | `llm_only:cot` | Structured plus a step-by-step reasoning section. | no | no |
| `llm_only_rag` | `llm_only:rag` | Structured, but the system-data block holds only the rows retrieved for the request. | no | no |
| `llm_only_nr` | `llm_only:nr` | Newton-Raphson worked by hand in the reasoning. Exploratory, not in the paper. | no | no |
| `llm_only_forced_structured` | `llm_only_forced:structured` | Structured without the abstention clause. The "LLM only, forced" row. | no | no |
| `llm_only_forced_cot` | `llm_only_forced:cot` | Chain-of-thought without the abstention clause. | no | no |
| `formulation_probe_structured` | `formulation_probe:structured` | Companion probe: declares the formulation only, no numbers. | no | no |
| `formulation_probe_cot` | `formulation_probe:cot` | Same, reasoning step by step first. | no | no |
| `single_call_structured` | `single_call:structured` | One function-calling round: every tool call at once, no memory, no second turn. | yes | observation gate |
| `single_call_few_shot` | `single_call:few_shot` | Single call plus two worked tool-call examples. | yes | observation gate |
| `single_call_cot` | `single_call:cot` | Single call plus a short numbered plan before the calls. | yes | observation gate |
| `single_call_rag` | `single_call:rag` | Single call with retrieved rows and tool descriptions. | yes | observation gate |
| `rule_based` | `rule_based` | Deterministic regex parser, no LLM. The conventional-workflow row. | yes | none |
| `react` | `react` | ReAct loop with the in-loop observation gate on every tool output. | yes | observation gate |
| `react_nogate` | `react_nogate` | ReAct loop, no gate. The plain multi-step agent. | yes | none |
| `plan_act` | `plan_act` | One planning call emits the whole tool plan, then it executes, with the observation gate. | yes | observation gate |
| `plan_act_nogate` | `plan_act_nogate` | Plan-and-Act, no gate. | yes | none |
| `pfagent` | `pfagent` | ReAct loop, no in-loop gate, plus the task-level verification gate V1 to V7 on the final answer. The solver-grounded row. | yes | final gate |
| `pfagent_obsgate` | `pfagent_obsgate` | Pre-verification PFAgent kept for the old stress numbers. | yes | observation gate |

Formulation for the prompting rows comes from a companion probe, `formulation_probe_structured` and
`formulation_probe_cot`: same case tables and request as the `llm_only` rows, but the only output is the
declared formulation (the ordered solver operations, in the tool vocabulary of `--tool-variant`), scored
with the same comparator as the tool rows. The answer prompts stay byte-identical to the paper runs:
asking for the formulation inside the answer made gpt-4o-mini's chain-of-thought stop abstaining
(2026-09-23, runs kept under `results/ieee14/2026-09-23/gpt-4o-mini/llm_only_*` and `*__f2`).

## Reading a method

```bash
.venv/bin/python run.py list-methods
.venv/bin/python run.py show-prompt --method pfagent            # card + assembled system prompt + hash
.venv/bin/python run.py show-prompt --method plan_act --tool-variant load_split   # also the planner prompt
```

## What is in a prompt and what is not

The `.txt` files hold every fixed sentence. Three things are still built by code at run time,
because they depend on the request or on the network, and `method.json` names them under
`dynamic_parts`:

- the system-data block (case tables rendered from the seed-perturbed network, or the rows
  RAG retrieved for the request), built in `llm/prompt_variants.py`;
- the two worked examples of the few-shot variants (`_FEW_SHOT_LLM_ONLY`,
  `_FEW_SHOT_SINGLE_CALL` in `llm/prompt_variants.py`);
- the tool schemas passed to the API (`llm/tools.py`, `--tool-variant v1|load_split`) and, for
  Plan-and-Act, the tool catalogue appended to `plan_act/plan_system_prompt_prefix.txt`.

## Adding a method

1. Create `methods/<name>/method.json` (copy a neighbour; `runner_name` must be a name
   `benchmarks/evaluate_llms.py --method` accepts, so a genuinely new architecture also needs
   an entry in `ARCH_METHODS` there or a new strategy in `llm/prompt_variants.py`).
2. Put its fixed texts in `methods/<name>/*.txt` and list them in `prompt_files`.
3. Add the new texts to `PINNED_TEXTS` in `tests/test_methods_prompts.py` once the wording is
   final.
