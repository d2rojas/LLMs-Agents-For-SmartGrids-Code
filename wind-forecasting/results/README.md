# results/

Every run of a method on the benchmark, laid out the way every case study lays its results out.
Everything here is tracked in git, traces included: these runs are the evidence behind the paper
table and travel with the repository.

```
results/
  INDEX.md, INDEX.json                one line per method folder, newest first (run.py index)
  sdwpf/                              the one instance set: five turbines x four windows of the SDWPF farm
    <YYYY-MM-DD>/                     the day the run was made
      <model>/                        gpt-4o-mini, gpt-5.6-sol, ..., no-llm for rule_based
        <method>[__<tag>]/            rule_based, llm_only_structured, llm_only_cot, plan_act_nogate,
                                      react_nogate, windagent; __smoke marks a set that is not the paper's, __stress the stress condition
          REPORT.md                   the outcome split, the metrics by group, the errors by horizon, failure lists, every request
          summary.csv                 one line per request, the same columns on every method
          summary.json                header + aggregate, the line INDEX.md prints
          config.json                 what was run: command, parameters, commit, prompt hash, GRU weights hash, cost
          requests.jsonl              the request set: id, text, turbine, window, horizon, question
          traces/
            NN_<request-id>.json            the trace the method left
            NN_<request-id>.transcript.txt  the exchange: system, request, every message, tool call, output, gate
            NN_<request-id>.narrative.txt   what happened, step by step, with the verdicts
            NN_<request-id>.png             the reported series against the target, when the series is valid
          raw/                        rows.jsonl (every scored field), traces/<request-id>.json, run.log
```

`NN` numbers the requests 01..N in request-id order, so the same request has the same number in
every method's folder of a run.

The three outcomes in every report are exclusive and sum to the request count:

- **Solved**: a valid series (exactly horizon x 6 finite values inside the physical range), an
  answer coherent with it, and, for the methods with tools, a series that is value for value a
  forecast-tool output or the mean of two. Forecast accuracy is never a term: no method can see
  the target days, so it lives in the MAE and RMSE columns.
- **Escalated**: the method declared cannot_forecast, or the budget ran out, or the gate rejected
  two attempts. Takes precedence. Under the stress condition (an incomplete last history day) it
  is the correct outcome and counts as solved.
- **Wrong, unflagged**: a series with the wrong length, a value outside the range, a series no tool
  produced (methods with tools), or an answer that contradicts its own series, presented as valid.

## Making a run

```bash
python run.py run --dry-run                                        # plan and cost, spends nothing
python run.py run --method windagent --n 3 --horizon 48 --tag smoke --model openrouter:openai/gpt-4o-mini
python run.py postprocess results/sdwpf/<date>/<model>/<method>    # re-render after a scoring change
python run.py rescore results/sdwpf/<date>/<model>/<method>        # re-score from the traces, then re-render
python run.py index
```

A request whose trace already exists in the folder is kept unless `--force`, so a run killed
half way resumes where it was.
