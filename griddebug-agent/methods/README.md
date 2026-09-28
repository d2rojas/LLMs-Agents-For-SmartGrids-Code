# methods/

One folder per evaluated method. Each folder holds a `method.json` saying what the method is, how
the runner names it and which texts it is built from, plus the `.txt` texts only that method uses.
Texts several methods share live in `_shared/`. The code lives by role: `agent/` (the ReAct loop,
the gate, Plan-and-Act, the model client), `prompting/` (the two no-tools methods),
`deterministic/` (the rule engine's policy); `answer.py` is the answer contract every method
returns and `common.py` the prompt assembly and the run record.

These files are the **only** copy of every prompt. `methods/common.py` reads them at call time, so
editing a `.txt` changes the prompt for every caller at once. `tests/test_methods_prompts.py` pins
the hash of every text; changing a prompt fails that test until the pin is updated on purpose,
because a silent wording change would make new runs incomparable with the ones already reported.

| folder | runner name | what it is | tools | gate |
|---|---|---|---|---|
| `rule_based` | `rule_based` | The rule engine classifies the evidence and a fixed policy acts, verifying with the power flow, inside the same budget. No LLM. The conventional-automation row. | yes | none |
| `llm_only_structured` | `llm_only:structured` | One call, no tools. The model writes the diagnosis, the actions and the state it expects; the harness applies the actions once. | no | none |
| `llm_only_cot` | `llm_only:cot` | The structured prompt plus one reasoning section. | no | none |
| `plan_act_nogate` | `plan_act_nogate` | One call emits the whole sequence of tool calls, executed without feedback, then one answer call. | yes | none |
| `react_nogate` | `react_nogate` | Tool call, observation, repeat, inside the budget. The original GridDebugAgent loop without the gate. | yes | none |
| `griddebug` | `griddebug` | The ReAct loop plus the verification gate G1–G7 on the final answer. The solver-grounded row. | yes | final gate |

These six are the design, in this order, the same six with the same names as every other case
study in the paper. Every method receives the same request, the same evidence block, the same
answer contract (`_shared/output_contract.txt`) and the same rules (`_shared/common_rules.txt`);
every method with tools receives the same catalogue (`solver/tools.py`); the methods without tools
receive that catalogue as text. One scorer (`evaluation/scoring.py`) reads every answer.

## What is in a `.txt` and what is not

Three parts of a prompt are built by code at run time, because they depend on the scenario, and
each `method.json` names them under `dynamic_parts`: the request (`evaluation/requests.py`), the
evidence block (`solver/evidence.py` plus the base network's violations), and the tool catalogue
(`solver/tools.py`, as schemas for the agents and as text for the others). The gated method also
receives the gate's verdict on its one retry.

## Reading a method

```bash
.venv/bin/python run.py list-methods
.venv/bin/python run.py show-prompt --method griddebug     # card, texts, assembled system prompt and its hash
```
