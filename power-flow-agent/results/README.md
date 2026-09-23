# results/

Every run of a method on a case, laid out so the past is easy to find and every number can
be traced to its trace. Everything in this tree is tracked in git, raw reports and traces
included: these runs are the evidence behind the paper tables and travel with the repository.

```
results/
  INDEX.md                                  one line per run directory, newest first (run.py index)
  <case>/                                   ieee14, ieee30, ...
    <YYYY-MM-DD>/                           the day the run was made
      <model>/                              gpt-4o-mini, gpt-5.6-sol, gpt-5.4, no-llm (rule_based)
        <method>[__stress][__<suffix>]/     methods/ folder name; __stress for the stress request set
          REPORT.md                         counts per metric, failure lists, cost; cross-checked against the runner
          summary.csv                       one line per run: request, formulation, outcome, verification, tokens, time
          summary.json                      the aggregate behind INDEX.md
          requests.jsonl                    the request set with the intended tool calls
          config.json                       exact command, parameters, git commit, prompt hash, provenance
          traces/
            NN_<request-id>.narrative.txt   what happened, step by step, with the verdicts
            NN_<request-id>.transcript.txt  the raw exchange: system prompt, request, every LLM message, tool call, tool output, gate verdict, final answer
            NN_<request-id>.json            the raw trace the runner wrote
          raw/                              the runner's own outputs: report.json, report.rescored.json, traces/<method>/<case>/*.json, run logs
```

`NN` numbers the runs 01..N in request-id order, so the same request has the same number
in every method's folder for a given case and request set.

## Reading a run

Start at `INDEX.md`, open the folder's `REPORT.md`, then the narrative of any run listed
under "Wrong and unflagged" or "Escalated". The transcript is the evidence for what the
narrative says.

The three outcomes in every report are exclusive and sum to the run count:

- **Solved autonomously**: the executed tool calls matched the request, the numbers match the
  reference, and the method answered on its own.
- **Escalated to a person**: the method declared it could not answer (abstained, hit the round
  limit, or the verification gate rejected every candidate). Escalation takes precedence over
  the other two.
- **Wrong, unflagged**: the method reported numbers that do not match the reference and did not
  say so.

## Making a run

```bash
.venv/bin/python run.py run --method pfagent --model openrouter:openai/gpt-4o-mini --case ieee14 --n 40 --dry-run
.venv/bin/python run.py run --method pfagent --method react_nogate --model openrouter:openai/gpt-4o-mini --case ieee14 --n 40
.venv/bin/python run.py postprocess results/ieee14/<date>/<model>/<method>    # re-render after a scoring change
.venv/bin/python run.py index
```

`run` calls `benchmarks/evaluate_llms.py` with the same flags as the paper runs, then
`benchmarks/rescore.py`, then `benchmarks/postprocess.py`. A run that already has
`raw/report.json` is skipped unless `--force`. `--dry-run` prints the plan and a cost
estimate from `pricing.json` without spending anything.

## Provenance of the migrated runs

Folders whose `config.json` has `"kind": "migrated"` were copied from
`benchmarks/results_*` by `scripts/migrate_paper_results.py` on 2026-09-23. Which runs: exactly
the ones `benchmarks/build_paper_tables.py` reads for the paper tables (main protocol table,
stress table, split-tool before/after appendix). `config.json` records the source directory,
the commit that last touched it, the role in the paper, and the tool variant. Their date is the
write time of the source `report.json`. Two runs of the same method on the same day from
different sources get a suffix: `__v1` / `__load_split` when the tool set differs,
`__from-<source>` otherwise.

Under `benchmarks/results_*` the raw `report.json` and `traces/` were gitignored, so a fresh
clone cannot rebuild the paper tables from there. Here they are tracked. The paper tables
themselves are still built from `benchmarks/results_*` by `benchmarks/build_paper_tables.py`;
this tree is the readable, complete mirror of those runs.
