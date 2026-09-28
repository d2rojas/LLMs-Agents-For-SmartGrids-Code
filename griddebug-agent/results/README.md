# results/

Every run of a method on a network, laid out the way every case study lays its results out.
Everything here is tracked in git, traces included: these runs are the evidence behind the paper
table and travel with the repository.

```
results/
  INDEX.md, INDEX.json                one line per method folder, newest first (run.py index)
  <instance>/                         ieee14, ieee30, ieee57
    <YYYY-MM-DD>/                     the day the run was made
      <model>/                        gpt-4o-mini, gpt-5.6-sol, ..., no-llm for rule_based
        <method>[__<tag>]/            rule_based, llm_only_structured, llm_only_cot, plan_act_nogate,
                                      react_nogate, griddebug; a __<tag> suffix marks a set that is not the paper's
          REPORT.md                   the outcome split, the metrics by group, failure lists, every scenario
          summary.csv                 one line per scenario, the same columns on every method
          summary.json                header + aggregate, the line INDEX.md prints
          config.json                 what was run: command, parameters, commit, prompt hash, cost
          requests.jsonl              the scenario set: id, request text, injected fault, initial state
          traces/
            NN_<request-id>.json            the trace the method left
            NN_<request-id>.transcript.txt  the exchange: system, request, every message, tool call, output, gate
            NN_<request-id>.narrative.txt   what happened, step by step, with the verdicts
          raw/                        rows.jsonl (every scored field), traces/<request-id>.json, run.log
```

`NN` numbers the scenarios 01..13 in request-id order, so the same scenario has the same number in
every method's folder of a run.

The three outcomes in every report are exclusive and sum to the scenario count:

- **Solved**: the harness's own power flow on the final network is secure (converged, no islanded
  load, no violation beyond the base network), the answer claims a repair, every number traces to a
  tool output or the evidence, and the answer's final_state agrees with the solver.
- **Escalated**: the method declared not_repaired or cannot_repair and listed what remains, or the
  budget ran out, or the gate rejected two attempts. Takes precedence.
- **Wrong, unflagged**: a repair claim the solver contradicts, an unsupported number, or no answer
  with the contract, presented as valid.

## Making a run

```bash
.venv/bin/python run.py run --dry-run                                        # plan and cost, spends nothing
.venv/bin/python run.py run --method griddebug --network case14 --model openrouter:openai/gpt-4o-mini
.venv/bin/python run.py postprocess results/ieee14/<date>/<model>/<method>   # re-render after a scoring change
.venv/bin/python run.py rescore results/ieee14/<date>/<model>/<method>       # re-score from the traces, then re-render
.venv/bin/python run.py index
```

A scenario whose trace already exists in the folder is kept unless `--force`, so a run killed
half way resumes where it was. Only the newest run set stays in the working tree; older ones live
in git history.
