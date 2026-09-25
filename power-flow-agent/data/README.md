# data/

- `matpower/<case>/<date>/<case>.m`: MATPOWER case files (IEEE 14, 30, 57, 118, 300 bus) as
  fetched by `data/fetch_matpower_cases.py`. `solver/case_loader.py` reads them; the
  benchmark perturbs loads and setpoints around the base case (`--k 1`) so the models cannot
  answer from memory.
- Requests are not stored here. `benchmarks/requests.py` generates them deterministically from
  (case, N, seed), so a run's request set is reproducible from its `config.json`; each run
  directory also writes the set it used to `requests.jsonl`. To freeze a set explicitly:

  ```bash
  .venv/bin/python -m benchmarks.requests --case case14 --n 40 --seed 0 --out data/requests_case14_n40_s0.jsonl
  .venv/bin/python run.py run --method pfagent --model openai:gpt-4o-mini --case ieee14 --requests data/requests_case14_n40_s0.jsonl
  ```
