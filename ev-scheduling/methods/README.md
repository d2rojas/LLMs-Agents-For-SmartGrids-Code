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
| `llm_only_structured` | `llm_only:structured` | The model answers from the request text alone: one JSON reply with the formulation it read, the schedule as charging segments, and the answer. | no | none | yes |
| `llm_only_cot` | `llm_only:chain_of_thought` | The structured prompt plus one reasoning section. | no | none | yes |
| `plan_act_nogate` | `plan_act` | One call emits the whole sequence of solver calls, then it executes. | yes | none | not yet |
| `react_nogate` | `react` | Tool call, observation, repeat, inside the round budget. | yes | none | not yet |
| `evagent` | `evagent` | The ReAct loop plus the verification gate E1–E7 on the final answer. The solver-grounded row. | yes | final gate | yes |

These six are the design, in this order, and they are the same six with the same names as every
other case study in the paper. A method that exists in one case study and not another cannot be
compared, so the set does not vary.

## One skeleton for the five methods that send a prompt

Every method that talks to a model sends the same four sections, in this order, built by the same
functions in `methods/prompting/strategies.py`:

| section | who writes it | differs between methods? |
|---|---|---|
| `## Role` | `_shared/llm_only_role.txt` or `_shared/agent_role.txt` | only in whether a solver exists |
| `## System Data` | `strategies.py::_context_section` | no, byte-identical |
| `## Task` | the request text, verbatim | no |
| `## Output Requirements` | `_shared/llm_only_output_contract.txt` or `_shared/agent_output_contract.txt`, both with `_shared/answer_rule.txt` filled in | only in what the architecture makes true |

Chain-of-thought adds `## Reasoning Instructions` between the task and the output requirements, and
that one section is the whole difference between the two prompting rows.

**Corrected on 2026-09-28.** Until that date the three agent rows were sent something else entirely:
a `GOAL` section stating the objective and a "serve at least 70 %" target, the constraint list in
index form, the whole session table, and the solver's own algorithm in three steps. The no-tools rows
were sent none of it, and a test asserts they still are not. Three of six rows were being helped by
their prompt, so a difference between those rows and these would have measured the scaffolding as
much as the architecture, which is precisely what reviewers R3.2 and R4.3 asked us to rule out.
Plan-and-Act, meanwhile, had been sent the bare request text with no sections at all, so the three
agent rows did not even match each other. All of that is gone; `tests/test_prompting.py` pins it.

The extraction prompt was corrected in the same commit. It used to give 50.0 kW, $0.45 and $0.12 per
kWh with the 4pm-9pm window, and 7.0 kW per plug, as defaults. Eighteen of the twenty frozen days
state a 50 kW cap and all twenty state those two prices, so a model that never read those sentences
would have got them right anyway, and the Formulation column would have been measuring the prompt.
Every field of the schema is `null` now, and the rules say to read the request and never to supply a
value from what is usual.

## What is in a `.txt` and what is not

The `.txt` files hold every fixed sentence. Three parts of a prompt are still built by code at run
time because they depend on the request, and each method's `method.json` names them under
`dynamic_parts`:

- **`## System Data`** — the time grid, the unit convention and the EV labels, from the day's
  horizon. It deliberately carries no session table, no site cap and no prices: those are in the
  request text, for the no-tools methods exactly as for the solver-grounded one, so that reading the
  request is part of what is being measured.
- **`## Task`** — the request text, verbatim.
- **`## Output Requirements`** — `_shared/llm_only_output_contract.txt` with the number of cars
  filled in. The contract is one JSON object: the `formulation` the model read (the same schema the
  agents' parse turn returns, so `evaluation/formulation.py` scores every method with one function),
  the `schedule` as charging segments `[start_hour, end_hour, power_kw]` per car, and the `answer`.
  Segments replaced the 96-number rows on 2026-09-28: on a day with 87 cars the rows did not fit in
  the model's output window, and every reply of the run of 2026-09-21 was cut off mid-row.

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
