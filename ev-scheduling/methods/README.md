# methods/

One folder per evaluated method. Each folder holds a `method.json` saying what the method is, how
the runner names it and which texts it is built from, plus the `.txt` texts only that method uses.
Texts several methods share live in `_shared/`.

These files are the **only** copy of every prompt. `methods/prompting/strategies.py`, `methods/agent/llm_agent.py`
and `methods/agent/parse/parse.py` read them at import time, so editing a `.txt` changes the prompt for the
benchmark and for every other caller at once. `tests/test_methods_prompts.py` pins the hash of every
text to the value the committed runs were produced with. Changing a prompt therefore fails a test
until the pin is updated on purpose, which is the point: a silent wording change would make new runs
incomparable with the ones already reported, and the scores would simply move with nothing to say
why.

| folder | runner name | what it is | tools | gate | runs |
|---|---|---|---|---|---|
| `rule_based` | `rule_based` | Regular expressions read the request, the solver does the rest. The conventional-automation row. | yes | none | not yet |
| `llm_only_structured` | `llm_only:structured` | The model answers from the request text alone and writes the kW matrix as text. | no | none | yes |
| `llm_only_cot` | `llm_only:chain_of_thought` | The structured prompt plus one reasoning section. | no | none | yes |
| `plan_act_nogate` | `plan_act` | One call emits the whole sequence of solver calls, then it executes. | yes | none | not yet |
| `react_nogate` | `react` | Tool call, observation, repeat, inside the round budget. | yes | none | not yet |
| `evagent` | `evagent` | The ReAct loop plus the verification gate E1–E6 on the final answer. The solver-grounded row. | yes | final gate | yes |

These six are the design, in this order, and they are the same six with the same names as every
other case study in the paper. A method that exists in one case study and not another cannot be
compared, so the set does not vary.

## What is in a `.txt` and what is not

The `.txt` files hold every fixed sentence. Three parts of a prompt are still built by code at run
time because they depend on the request, and each method's `method.json` names them under
`dynamic_parts`:

- **`## System Data`** — the time grid, the unit convention and the EV labels, from the day's
  horizon. It deliberately carries no session table, no site cap and no prices: those are in the
  request text, for the no-tools methods exactly as for the solver-grounded one, so that reading the
  request is part of what is being measured.
- **`## Task`** — the request text, verbatim.
- **`## Output Requirements`** — the row count, the step count, and whether an answer line is
  demanded, which depends on whether the request asks something checkable.

## Whitespace is significant

`methods.read_text` strips exactly one trailing newline, the one an editor adds, and nothing else.
Two texts begin with a space because they are appended to a sentence rather than joined to it. Do
not reflow, re-indent or trim these files; a diff that looks like tidying changes the prompt and
fails the pin.

## Reading a method

```python
import methods
methods.cards()                                   # every method, in table order
methods.card("evagent")["dynamic_parts"]          # what code still builds at run time
methods.texts("llm_only_cot")                     # (path, contents) for each text it uses
```
