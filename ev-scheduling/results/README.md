# results/

Every run of a method on the charging site, laid out the way every case study lays its results
out, so a reader who knows one tree knows this one. Everything here is tracked in git, traces
included: these runs are the evidence behind the paper table and travel with the repository.

```
results/
  INDEX.md, INDEX.json                one line per method folder, newest first (run.py index)
  <instance>/                         caltech: the charging site the frozen days come from
    <YYYY-MM-DD>/                     the day the run was made
      <model>/                        gpt-4o-mini, gpt-5.6-sol, ..., no-llm for the reference rows
        <method>/                     rule_based, llm_only_structured, llm_only_cot, plan_act_nogate,
                                      react_nogate, evagent; and the two reference rows, optimum and charge_asap
          REPORT.md                   the method's outcome split, rates, cost, failure lists, every request
          summary.csv                 one line per request, the same columns on every method
          summary.json                header + aggregate, the line INDEX.md prints
          config.json                 what was run, the request digest, the command, the commit
          requests.jsonl              the request set, one list for every method of the run
          traces/
            NN_<request-id>.json            the raw trace the runner wrote
            NN_<request-id>.transcript.txt  the exchange: system, request, every message, tool call, output, verdict
            NN_<request-id>.narrative.txt   what happened, step by step, with the verdicts
          raw/                        the run set this folder was built from: rows.csv, scoreboard, manifest
```

`NN` numbers the requests 01..N in request-id order, so the same request has the same number in
every method's folder of a run.

## Reading a run

Start at `INDEX.md`, open a method's `REPORT.md`, then the narrative of any request listed under
"Wrong and unflagged" or "Escalated". The transcript is the evidence for what the narrative says.

The three outcomes in every report are exclusive and sum to the request count:

- **Solved**: the state is right (no hard violation, cost gap within tolerance, and the gap not
  bought by leaving energy undelivered), every number traces to the last solve, and the answer
  matches what was asked when the request asks something checkable.
- **Escalated**: the method declared it could not answer instead of presenting a schedule as
  valid. Takes precedence over the other two.
- **Wrong, unflagged**: an invalid schedule, a number with no support, or a misread request,
  presented as valid.

## Making a run

```bash
python run.py run --dry-run --days 20 --data-source cache     # cost estimate, spends nothing
python run.py run --days 20 --data-source cache               # every method on the frozen days
python run.py postprocess results/ev_matrix_<model>           # lay a run set out here (run does this itself)
python run.py index
```

The runner writes a run set, `results/ev_matrix_<model>/`, with every method's rows in one file;
`postprocess` lays it out as the method folders above and copies the run set's own files into each
folder's `raw/`. After that the run-set directory is not needed in the working tree.

## What stays in the working tree

Only the newest run stays checked out. Older runs live in git history, where every number of the
paper can still be traced to its trace; keeping them all in the tree made the newest one hard to
find. The first run of this case study (2026-09-21, gpt-4o-mini, five methods) is the one here.
