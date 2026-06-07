# Midway Report: Deliverables

**ECE 285 Project — Agentic EV Charging Schedule Assistant**  
**Group #10**: Ryan Luo, Peter Quawas

This document describes **what each file does**, **how it works**, and the **current status** of midway deliverables. It is structured in three parts: **Part I** (completed Phase A), **Part II** (completed Phase B), and **Part III** (completed Phase C).

---

## Table of contents

1. [Part I — Completed (Phase A)](#part-i--completed-phase-a)
   - 1.1 [Standardized session format](#11-standardized-session-format-dataformat)
   - 1.2 [Data loader](#12-data-loader-dataloader)
   - 1.3 [Config](#13-config-config)
   - 1.4 [Constraint checker](#14-constraint-checker-constraints)
   - 1.5 [Optimization solver](#15-optimization-solver-optimization)
   - 1.6 [Evaluation metrics](#16-evaluation-metrics-evaluationmetrics)
   - 1.7 [Visualization](#17-visualization-visualization)
   - 1.8 [Phase A script](#18-phase-a-script-scriptsrun_phase_apy)
   - 1.9 [Tests](#19-tests-tests)
   - 1.10 [End-to-end data flow](#110-end-to-end-data-flow-phase-a)
2. [Part II — Completed (Phase B)](#part-ii--completed-phase-b)
   - 2.1 [Baseline module](#21-baseline-module-baseline)
   - 2.2 [Evaluation script for baseline](#22-evaluation-script-for-baseline)
   - 2.3 [End-to-end data flow](#23-end-to-end-data-flow-phase-b)
3. [Part III — Completed (Phase C)](#part-iii--completed-phase-c)
   - 3.1 [Agent modules](#31-agent-modules-agent)
   - 3.2 [Agent script and visualization](#32-agent-script-and-visualization)
   - 3.3 [End-to-end data flow](#33-end-to-end-data-flow-phase-c)
4. [Reference: Midway checklist](#reference-midway-deliverable-checklist)

---

# Part I — Completed (Phase A)

## 1.1 Standardized session format (`data/format/`)

### File: `data/format/schema.py`

**Purpose**  
Defines the single canonical data shape for one day of EV charging sessions. Every other module (loader, checker, solver, baseline, agent) uses these types so that session order, time convention, and units are consistent.

**What it does**
- Exposes two dataclasses and two constants.
- **`Session`** (frozen): One EV visit. Fields: `session_id`, `arrival_idx`, `departure_idx`, `energy_kwh`, `charger_id`, `max_power_kw`. Validation in `__post_init__`: indices non-negative and ordered, energy and max_power positive.
- **`DaySessions`**: One day. Fields: `sessions` (list of `Session`), `n_steps` (number of time steps), `dt_hours` (duration of one step, default 0.25). Validation: `n_steps` and `dt_hours` positive; every session has `departure_idx ≤ n_steps`.
- **`DEFAULT_DT_HOURS`** = 0.25, **`DEFAULT_STEPS_PER_HOUR`** = 4.

**How it works**
- Time is **discrete**: step indices `0 .. n_steps-1`. Charging is allowed only for steps `t` in the half-open interval **[arrival_idx, departure_idx)**.
- Units: power in **kW**, energy in **kWh**. Schedule matrices have shape `(n_sessions, n_steps)` with the same order as `day.sessions`.

**Consumers**  
Loader (output), checker (input), solver (input), metrics (input), visualization (input), baseline/agent (input).

---

## 1.2 Data loader (`data/loader/`)

### File: `data/loader/loader.py`

**Purpose**  
Fetch charging sessions from the Caltech ACN-Data API for a given site and date, and convert them into the project's standardized format (`DaySessions`). No synthetic data; API key required.

**What it does**
- **`load_sessions(site_id, day_date, api_token=None, n_steps=96, dt_hours=0.25)`**  
  - Reads `ACN_DATA_API_TOKEN` from `api_token` or environment if not provided.  
  - Builds a UTC date range: midnight of `day_date` to midnight of the next day.  
  - Calls the Eve API with a **MongoDB-style JSON** `where` clause: `{"$and": [{"connectionTime": {"$gte": "<RFC1123 start>"}}, {"connectionTime": {"$lte": "<RFC1123 end>"}}]}` (URL-encoded). The ev.caltech.edu API expects this format; the acnportal `DataClient` uses a different string format and is not used.  
  - Sends `GET` to `https://ev.caltech.edu/api/v1/sessions/<site_id>?where=...&sort=connectionTime&max_results=100` with HTTP Basic auth (token as username, empty password).  
  - Handles 401/403 and `_error` in the JSON body; raises `ValueError` with a clear message.  
  - Iterates `_items` and follows `_links.next` for pagination.  
  - For each raw session dict, calls `raw_session_to_standard(...)` and collects `Session` objects.  
  - Returns `DaySessions(sessions=..., n_steps=n_steps, dt_hours=dt_hours)`.

- **`raw_session_to_standard(raw, day_start_utc, dt_hours, n_steps)`**  
  - **Input**: One API session dict (keys: `connectionTime`, `disconnectTime`, `kWhDelivered`, `sessionID`, `spaceID`; optional `maxPower`).  
  - **Helper** `_parse_session_time(value, day_start_utc)`: Converts API time (RFC 1123 string or datetime) to seconds since `day_start_utc`; then converts to step indices.  
  - Converts connection/disconnect times to `arrival_idx` and `departure_idx` (clamped to `[0, n_steps]`).  
  - Reads `kWhDelivered` as requested energy (default 1.0 if missing/zero); uses `DEFAULT_MAX_POWER_KW` (7.0) if max power is missing or invalid.  
  - **Output**: One `Session` instance.

**How it works**
- All times are interpreted relative to **midnight UTC** for the requested calendar day. The API returns sessions whose `connectionTime` falls in that UTC window.
- Session order in `DaySessions` matches the API response order (sorted by `connectionTime` via `sort=connectionTime`).

---

## 1.3 Config (`config/`)

### File: `config/site.py`

**Purpose**  
Central place for site-level constraints and time-of-use (TOU) energy rates. Used by the optimizer, constraint checker, evaluation, and (later) baseline and agent so that all use the same horizon and costs.

**What it does**
- **`SiteConfig`**  
  - **Attributes**: `P_max_kw` (float or array of length `n_steps`), `n_steps`, `dt_hours` (default 0.25).  
  - **Method** `get_P_max_at_step(t)`: Returns the power cap in kW at step `t` (scalar or `P_max_kw[t]`).  
  - Used to enforce: at each time step `t`, total power ≤ P_max(t).

- **`TOUConfig`**  
  - **Attributes**: `rates_per_kwh` (1D array of length `n_steps`; $/kWh per step).  
  - **Property** `n_steps`: `len(rates_per_kwh)`.  
  - Used in the objective: minimize ∑_t c(t) × (total power at t) × dt.

- **`default_tou_rates(n_steps, peak_price=0.45, off_peak_price=0.12)`**  
  - Builds a rate vector of length `n_steps`. Step 0 = midnight. Peak window 4pm–9pm (steps 64–84 for 96 steps) gets `peak_price`; all other steps get `off_peak_price`.  
  - Returns a numpy array; typically wrapped as `TOUConfig(rates_per_kwh=default_tou_rates(day.n_steps))`.

**How it works**
- Callers (solver, checker, scripts) build `SiteConfig` and `TOUConfig` from the same `day.n_steps` and `day.dt_hours` so horizon and step duration are consistent.

---

## 1.4 Constraint checker (`constraints/`)

### File: `constraints/checker.py`

**Purpose**  
Verify that a given schedule (a matrix of power values) satisfies all problem constraints: availability, per-charger limits, site power cap, and energy delivery. Used to validate optimizer output and (later) baseline output.

**What it does**
- **`check(schedule, day, site, dt_hours=None, tol=None)`**  
  - **Inputs**: `schedule` shape `(n_sessions, n_steps)` (kW); `day` (`DaySessions`); `site` (`SiteConfig`); optional `dt_hours` (defaults to `day.dt_hours`); optional `tol` (defaults to `DEFAULT_TOL = 1e-5`).  
  - **Output**: `CheckResult`: `feasible` (bool), `violations` (list of `Violation`), `unmet_energy_kwh` (per-session array), `peak_load_kw` (float).

- **`Violation`** dataclass: `kind` ("availability" | "per_charger" | "site_cap" | "energy"), `session_id`, `time_step`, `message` (string with numeric details for debugging).

**How it works**
- Single pass over sessions and time steps:  
  - For each (session i, step t): read `p = schedule[i, t]`. Accumulate `total_power[t]` and per-session `delivered`.  
  - **Availability**: If `t < arrival_idx` or `t >= departure_idx` and `|p| > tol`, record an availability violation.  
  - **Per-charger**: If `p < -tol` or `p > max_power_kw + tol`, record a per_charger violation.  
  - **Energy**: After the loop over t for session i, compute `unmet_i = energy_kwh - delivered`. If `unmet_i < -tol` (over-delivery) or `unmet_i > tol` (under-delivery), record an energy violation. Store `unmet_energy_kwh[i] = max(0, unmet_i)`.  
- Second pass over t: if `total_power[t] > P_max(t) + tol`, record a site_cap violation.  
- **Feasible** = True iff `len(violations) == 0`. **peak_load_kw** = max of `total_power`.  
- Using `DEFAULT_TOL = 1e-5` avoids treating tiny solver numerical errors as violations (CVXPY typically achieves ~1e-8).

---

## 1.5 Optimization solver (`optimization/`)

### File: `optimization/solver.py`

**Purpose**  
Compute an optimal charging schedule that minimizes TOU energy cost plus a penalty for unmet energy, subject to availability, per-charger limits, site cap, and energy balance. This is the core "optimizer" used by Phase A and (later) by the agent.

**What it does**
- **`solve(day, site, tou, penalty_unmet=1e6)`**  
  - **Inputs**: `day` (`DaySessions`), `site` (`SiteConfig`), `tou` (`TOUConfig`), `penalty_unmet` (M in the objective, $/kWh).  
  - **Output**: `SolveResult`: `schedule` (numpy array, shape `(n_sessions, n_steps)`), `total_cost_usd`, `unmet_energy_kwh` (per session), `peak_load_kw`, `success` (bool), `message` (optional error/status string).

**How it works**
1. **Dimensions**: `n_sessions = len(day.sessions)`, `n_steps = day.n_steps`, `dt = day.dt_hours`, `c = tou.rates_per_kwh`. If `n_sessions == 0` or `n_steps == 0`, return a zero schedule and success.
2. **Variables**: CVXPY variables `p` (shape `(n_sessions, n_steps)`, nonnegative) and `u` (length `n_sessions`, nonnegative). `p[i,t]` = power (kW) to session i at step t; `u[i]` = slack/unmet energy (kWh) for session i.
3. **Objective**: Minimize `∑_t c(t)·(∑_i p[i,t])·dt + penalty_unmet·∑_i u[i]`.
4. **Constraints**:  
   - Availability: for each (i, t) with t outside [arrival_idx, departure_idx), `p[i,t] == 0`; else `p[i,t] <= max_power_kw`.  
   - Site cap: for each t, `∑_i p[i,t] <= site.get_P_max_at_step(t)`.  
   - Energy: for each i, `∑_t p[i,t]*dt + u[i] == sess.energy_kwh`.
5. **Solve**: `cp.Problem(objective, constraints).solve()`. On exception or non-optimal status, return a failed `SolveResult` with message.
6. **Extract**: `schedule = max(p.value, 0)`, `unmet = max(u.value, 0)`. Compute `total_cost_usd` and `peak_load_kw` from the schedule for reporting.

---

## 1.6 Evaluation metrics (`evaluation/metrics/`)

### File: `evaluation/metrics/__init__.py`

**Purpose**  
Provide standard metrics for any schedule: total energy cost, total unmet energy, peak load, % of sessions fully served, and (optionally) % cost reduction versus an uncontrolled (charge-asap) baseline. Used by the Phase A script and will be used by baseline and agent evaluation.

**What it does**
- **`total_cost(schedule, tou, dt_hours)`**  
  - Formula: ∑_t c(t)·(∑_i schedule[i,t])·dt_hours. Returns total cost in $.

- **`total_unmet_kwh(schedule, day, dt_hours)`**  
  - For each session i, delivered = ∑_t schedule[i,t]·dt_hours; unmet = max(0, energy_kwh - delivered). Returns the sum of unmet over all sessions.

- **`peak_load_kw(schedule)`**  
  - Returns max over t of (sum over i of schedule[i,t]).

- **`pct_fully_served(schedule, day, dt_hours)`**  
  - Count of sessions for which delivered ≥ requested (within a small tolerance). Returns 100·count / len(sessions).

- **`charge_asap_schedule(day, site_p_max)`**  
  - Builds an uncontrolled schedule: for each session, from `arrival_idx` to `departure_idx`, charge at `min(max_power_kw, remaining/dt)` until requested energy is met. Returns a schedule array of the same shape. Used only to compute the uncontrolled cost for comparison.

- **`compute_metrics(schedule, day, tou, dt_hours, violation_count=0, uncontrolled_cost_usd=None)`**  
  - Calls the above to fill a **`Metrics`** dataclass: `total_cost_usd`, `total_unmet_kwh`, `peak_load_kw`, `violation_count`, `pct_fully_served`, and (if `uncontrolled_cost_usd` is provided) `cost_reduction_vs_uncontrolled_pct` = 100·(uncontrolled - cost) / uncontrolled.

**How it works**
- All functions assume `schedule` has shape `(n_sessions, n_steps)` with session order matching `day.sessions`. Empty schedules or zero-length days are handled (return 0 or 0.0 as appropriate).

---

## 1.7 Visualization (`visualization/`)

### File: `visualization/plots.py`

**Purpose**  
Produce two kinds of figures for reports and debugging: a schedule heatmap (sessions × time) and a facility load profile (total power vs time). Used by the Phase A script; will be reused for baseline and agent outputs.

**What it does**
- **`plot_schedule(schedule, day, save_path=None)`**  
  - If `schedule` is empty: creates a minimal figure with axes, optionally saves, then closes.  
  - Otherwise: creates a figure and axes, calls `ax.imshow(schedule, aspect="auto", ...)` with colormap `viridis` (rows = sessions, columns = time step; color = power in kW). Adds axis labels and a colorbar. If `save_path` is set, saves the figure (e.g. PNG) and closes it to free memory.

- **`plot_load_profile(schedule, day, save_path=None, title=None)`**  
  - Computes `load_per_t = np.sum(schedule, axis=0)` (total power at each time step). If schedule is empty, uses zeros of length `day.n_steps`.  
  - Plots time step index vs load (line plot). Sets xlabel "Time step", ylabel "Total load (kW)". Optional title; optional save and close.

**How it works**
- Both functions import `matplotlib.pyplot` locally. They do not show the plot interactively; they save to file and close the figure so that batch runs do not accumulate figures.

---

## 1.8 Phase A script (`scripts/run_phase_a.py`)

**Purpose**  
Single entry point to run the full Phase A pipeline from the command line: load sessions from the API, solve, check constraints, compute metrics (including comparison to uncontrolled), print results and any violations, and save schedule and load profile plots.

**What it does**
- **CLI**: `--site` (default `caltech`), `--date` (default yesterday; format YYYY-MM-DD).
- **Environment**: Loads `.env` from project root (for `ACN_DATA_API_TOKEN`). No synthetic data; if the API returns no sessions, the script exits with a clear message.

**How it works (step-by-step)**
1. Parse arguments; resolve `day_date`.
2. Call `load_sessions(site_id, day_date)`. On `ValueError` or `ImportError`, print error and exit.
3. If `len(day.sessions) == 0`, print message suggesting another date and exit.
4. Build `SiteConfig(P_max_kw=50, n_steps=day.n_steps, dt_hours=day.dt_hours)` and `TOUConfig(rates_per_kwh=default_tou_rates(day.n_steps))`.
5. Call `solve(day, site, tou)`. If not `result.success`, print message and exit.
6. Call `check(result.schedule, day, site)`.
7. Compute uncontrolled schedule with `charge_asap_schedule(day, site_p_max)` and its cost with `total_cost(...)`. Call `compute_metrics(..., violation_count=len(check_result.violations), uncontrolled_cost_usd=...)`.
8. Print: Feasible, violations (if any) with kind/session/time/message, then total cost, peak, total unmet, % fully served, % cost reduction vs uncontrolled.
9. If `experiments/` exists, call `plot_schedule` and `plot_load_profile` and save to `experiments/phase_a_schedule.png` and `experiments/phase_a_load.png`.

**Usage**  
From project root with venv active:  
`python -m scripts.run_phase_a --site caltech --date 2019-06-15`

---

## 1.9 Tests (`tests/`)

### File: `tests/test_constraints.py`

**Purpose**  
Unit tests for the constraint checker so that feasible and infeasible schedules are correctly classified and violation types are identified.

**What it does**
- **`test_check_feasible_schedule`**: Builds a small `DaySessions` (2 sessions, 8 steps) and a schedule that satisfies availability, per-charger, site cap, and energy. Asserts `result.feasible` and no violations.
- **`test_check_availability_violation`**: One session; schedule has nonzero power at a time step outside [arrival, departure). Asserts not feasible and at least one violation with `kind == "availability"`.
- **`test_check_per_charger_violation`**: Schedule has power above `max_power_kw` at one step. Asserts violation kind `"per_charger"`.
- **`test_check_site_cap_violation`**: Two sessions; both charge at max in the same window so total power exceeds `P_max`. Asserts violation kind `"site_cap"`.
- **`test_check_energy_violation`**: Schedule delivers zero energy to a session that requested positive energy. Asserts not feasible, positive unmet for that session, and an energy violation.

**How it works**  
Tests construct `Session`, `DaySessions`, and `SiteConfig` by hand and pass a numpy schedule and the checker; they do not call the API or the solver.

---

## 1.10 End-to-end data flow (Phase A)

```
.env (ACN_DATA_API_TOKEN)
        │
        ▼
scripts/run_phase_a.py  ──►  data/loader/loader.py  ──►  DaySessions (list of Session)
        │                              │
        │                              └── raw_session_to_standard() per API item
        │
        ├── config/site.py  ──►  SiteConfig, TOUConfig (default_tou_rates)
        │
        ├── optimization/solver.py  ──►  SolveResult (schedule, cost, unmet, peak)
        │
        ├── constraints/checker.py  ──►  CheckResult (feasible, violations, unmet, peak)
        │
        ├── evaluation/metrics  ──►  charge_asap_schedule(), total_cost(), compute_metrics()
        │
        └── visualization/plots.py  ──►  plot_schedule(), plot_load_profile()  ──►  experiments/*.png
```

---

# Part II — Completed (Phase B)

Phase B implements the **direct LLM prompting baseline** and an **evaluation script** that runs it and reports the same metrics as Phase A.

## 2.1 Baseline module (`baseline/`)

### File: `baseline/prompt.py`

**Purpose**  
Build the single prompt string sent to the LLM so it can output a charging schedule.

**What it does**
- **`build_prompt(day, site, tou, instruction=None)`** → `str`  
  - Assembles a comprehensive prompt with three main parts:
    1. **Problem description**: objective (minimize TOU cost while meeting energy demand), time discretization (n_steps, dt_hours), site power cap P_max (via `_format_site_cap`), and TOU rate summary (via `_format_rates_summary`).
    2. **Session table**: Pipe-delimited table with columns `session_index`, `session_id`, `arrival_idx`, `departure_idx`, `energy_kwh`, `charger_id`, `max_power_kw`. One row per session in the same order as `day.sessions`.
    3. **Output specification**: Clear format instructions requiring `Session i: p0 p1 p2 ...` lines with exactly n_steps floating-point power values.
  - If `instruction` is provided, appends it as additional user guidance.

- **`_format_rates_summary(tou)`** → `str`  
  - Returns a human-readable summary of the TOU rates (min, max, mean $/kWh).

- **`_format_site_cap(site)`** → `str`  
  - Returns a human-readable description of the site power cap (constant or time-varying).

- **`_format_table(headers, rows)`** → `str`  
  - Renders a pipe-delimited markdown-style table for easy parsing by the LLM.

**How it works**
- The prompt instructs the LLM to output a machine-readable schedule matrix. Session order in the output must match `day.sessions`. The format is strictly specified to simplify parsing.

---

### File: `baseline/parse.py`

**Purpose**  
Convert the LLM's reply (plain text) into a schedule matrix that the checker and metrics can use.

**What it does**
- **`ParseResult`** dataclass: `schedule` (numpy array shape `(n_sessions, n_steps)`), `success` (bool), `error_message` (optional string).

- **`parse_llm_schedule(response_text, day)`** → `ParseResult`  
  - Parses lines matching the pattern `Session i: v0 v1 ... v_{n_steps-1}`.
  - Extracts session index from the left side of the colon, parses floating-point values from the right side.
  - Validates: session index in range, no duplicates, exactly n_steps values per line.
  - On trivial day (no sessions or no steps), returns a zero schedule with `success=True`.

- **`_fallback_matrix_parse(lines)`** (internal)  
  - Fallback parser for when the model omits `Session i:` prefixes but still outputs a numeric matrix.
  - Treats each line with exactly n_steps floats as one session row (in order).

**How it works**
- The parser is deliberately robust: ignores non-matching lines, tolerates extra whitespace, and provides clear error messages. If no valid session lines are found, it tries the fallback matrix parse before giving up.

---

### File: `baseline/run.py`

**Purpose**  
Single entry point: build prompt, call the LLM, parse response into a schedule.

**What it does**
- **`BaselineResult`** dataclass: `schedule`, `parse_success`, `raw_response`, `parse_error`.

- **`run_baseline(day, site, tou, api_key=None, model="gpt-4o-mini", max_completion_tokens=2048)`** → `BaselineResult`  
  - **Input validation**: Checks that `tou.n_steps`, `site.n_steps`, and `day.n_steps` all match; verifies `dt_hours > 0`.
  - **Trivial case**: If no sessions or no steps, returns a zero schedule immediately (no LLM call).
  - **API key**: Resolves from `api_key` argument or `OPENAI_API_KEY` environment variable. If missing, returns a failed result with a clear error message.
  - **Prompt**: Calls `build_prompt(day, site, tou)` to create the user message.
  - **LLM call**: Uses the `openai` Python client to call `chat.completions.create` with:
    - A system message instructing the model to output only schedules in the specified format.
    - The user message with the full prompt.
    - `temperature=0.0` for deterministic output.
    - `max_tokens=max_completion_tokens` to bound output size.
  - **Parse**: Calls `parse_llm_schedule(response_text, day)` to extract the schedule.
  - **Returns**: `BaselineResult` with schedule, parse status, raw response, and any error.

- **`_default_schedule(day)`** → `np.ndarray`  
  - Returns a zero schedule with the correct shape for the given day.

**How it works**
- The function is defensive: catches `ImportError` for missing `openai` package, catches exceptions from the API call, and handles empty API responses. The `max_completion_tokens` parameter defaults to 2048 to prevent unbounded output.

**Dependencies**
- `openai>=1.0.0` in `requirements.txt`.
- `OPENAI_API_KEY` documented in `.env.example`.

---

## 2.2 Evaluation script for baseline

### File: `scripts/run_baseline.py`

**Purpose**  
Run the baseline for a given site/date and output the same metrics as Phase A (cost, peak, unmet, % fully served, % cost reduction vs uncontrolled), plus feasibility and violations.

**What it does**
- **CLI**: `--site` (default `caltech`), `--date` (default yesterday), `--model` (default `gpt-4o`), `--max-tokens` (default 1024).
- **Environment**: Loads `.env` from project root (for `ACN_DATA_API_TOKEN` and `OPENAI_API_KEY`).

**How it works (step-by-step)**
1. Parse arguments; resolve `day_date`.
2. Call `load_sessions(site_id, day_date)`. On error, print message and exit.
3. If no sessions returned, print message and exit.
4. Build `SiteConfig(P_max_kw=50, n_steps=day.n_steps, dt_hours=day.dt_hours)` and `TOUConfig(rates_per_kwh=default_tou_rates(day.n_steps))` (same as Phase A).
5. Call `run_baseline(day, site, tou, model=args.model, max_completion_tokens=args.max_tokens)`.
6. If parse was not successful, print warning but continue.
7. Call `check(schedule, day, site)` to validate constraints.
8. Compute uncontrolled schedule with `charge_asap_schedule` and its cost with `total_cost`. Call `compute_metrics(..., violation_count=len(check_result.violations), uncontrolled_cost_usd=...)`.
9. Print results: feasibility, violation count, total cost, total unmet, peak load, % fully served, % cost reduction vs uncontrolled.
10. If there are violations, print the first 10 with details.

**Usage**  
From project root with venv active:  
`python -m scripts.run_baseline --site caltech --date 2019-06-15 --model gpt-4o`

**Reuse**  
All metrics and the checker from Phase A; no new metric code needed.

---

## 2.3 End-to-end data flow (Phase B)

```
.env (ACN_DATA_API_TOKEN, OPENAI_API_KEY)
        │
        ▼
scripts/run_baseline.py  ──►  data/loader/loader.py  ──►  DaySessions (list of Session)
        │
        ├── config/site.py  ──►  SiteConfig, TOUConfig (default_tou_rates)
        │
        ├── baseline/prompt.py  ──►  build_prompt()  ──►  prompt string
        │
        ├── baseline/run.py  ──►  OpenAI API call  ──►  raw response text
        │
        ├── baseline/parse.py  ──►  parse_llm_schedule()  ──►  schedule matrix
        │
        ├── constraints/checker.py  ──►  CheckResult (feasible, violations)
        │
        └── evaluation/metrics  ──►  compute_metrics()  ──►  Metrics (cost, peak, unmet, %)
```

---

# Part III — Completed (Phase C)

Phase C implements the **agentic pipeline** (Plan → Optimize → Validate → Refine → Explain) by wiring existing components and adding thin agent modules and a run script.

## 3.1 Agent modules (`agent/`)

### File: `agent/plan/plan.py`

**Purpose**  
Turn a user request into a structured plan (day, site, tou, objective) for the optimizer and checker.

**What it does**
- **`PlanResult`** dataclass: `day`, `site`, `tou`, `objective` (string), `raw` (optional).

- **`plan(request, day, site, tou)`** → `PlanResult`  
  - For v1, this is a simple pass-through: the request string is stored in `raw` but not parsed.
  - Returns `PlanResult(day=day, site=site, tou=tou, objective="minimize_cost", raw=request)`.
  - Future versions may use an LLM to extract custom objectives or constraint modifications from natural-language requests.

**How it works**
- The function accepts a natural-language request but currently ignores its content (pass-through for v1). The objective is always `"minimize_cost"`.

---

### File: `agent/optimize/call_solver.py`

**Purpose**  
Call the optimization solver from the agent with a consistent interface.

**What it does**
- **`optimize(day, site, tou, penalty_unmet=1e6)`** → `SolveResult`  
  - Thin wrapper around `optimization.solver.solve`.
  - Returns the `SolveResult` with schedule, cost, unmet, peak, and success flag.

**How it works**
- Simply calls `solve(day, site, tou, penalty_unmet)` and returns the result. Exists so the agent has a consistent interface and future versions can add objective selection or parameter tuning.

---

### File: `agent/validate/validate.py`

**Purpose**  
Run the constraint checker on the agent's schedule.

**What it does**
- **`validate(schedule, day, site)`** → `CheckResult`  
  - Thin wrapper around `constraints.checker.check`.
  - Validates availability, per-charger limits, site power cap, and energy delivery.

**How it works**
- Simply calls `check(schedule, day, site)` and returns the result. Exists so the agent has a consistent validation interface.

---

### File: `agent/refine/refine.py`

**Purpose**  
On solver failure or validation failures, optionally adjust inputs and re-solve.

**What it does**
- **`refine(day, site, tou, solve_result, max_retries=1)`** → `(DaySessions, SiteConfig, TOUConfig, SolveResult)`  
  - For v1, this is a simple pass-through: returns the inputs unchanged.
  - Future versions may implement refinement strategies such as:
    - Relaxing the site power cap if the solver fails.
    - Reducing energy demands if they cannot be met.
    - Adjusting session windows to resolve conflicts.

**How it works**
- Currently returns `(day, site, tou, solve_result)` unchanged. The `max_retries` parameter is accepted but unused in v1.

---

### File: `agent/explain/explain.py`

**Purpose**  
Turn numeric results into a short natural-language explanation that uses only computed facts (grounded).

**What it does**
- **`ScheduleFacts`** dataclass: `total_cost_usd`, `peak_load_kw`, `total_unmet_kwh`, `cost_reduction_vs_uncontrolled_pct` (optional).

- **`extract_facts(schedule, total_cost_usd, peak_load_kw, total_unmet_kwh, uncontrolled_cost_usd=None)`** → `ScheduleFacts`  
  - Builds a `ScheduleFacts` dataclass from the given metrics.
  - If `uncontrolled_cost_usd` is provided, computes `cost_reduction_vs_uncontrolled_pct = 100 * (uncontrolled - cost) / uncontrolled`.

- **`generate_explanation(facts, use_llm=False)`** → `str`  
  - For v1, uses a template string: "Total cost: $X. Peak load: Y kW. Unmet energy: Z kWh. Cost reduction vs uncontrolled: W%."
  - The `use_llm` parameter is accepted but unused in v1.

**How it works**
- Explanations are strictly grounded in numeric facts. No hallucination is possible because the template only uses computed values from `ScheduleFacts`.

---

### File: `agent/run.py`

**Purpose**  
Run the full agent pipeline once: plan → optimize → validate → optionally refine → explain.

**What it does**
- **`AgentResult`** dataclass: `schedule`, `total_cost_usd`, `peak_load_kw`, `unmet_energy_kwh`, `feasible`, `explanation`.

- **`run_agent(day, site, tou, request="Minimize energy cost for this day.", max_retries=1)`** → `AgentResult`  
  - Orchestrates the full pipeline:
    1. **Plan**: Call `plan(request, day, site, tou)` to get structured inputs.
    2. **Optimize**: Call `optimize(day, site, tou)` to compute the schedule.
    3. **Validate**: Call `validate(schedule, day, site)` to check constraints.
    4. **Refine**: If solver failed and `max_retries > 0`, call `refine(...)` and re-validate (v1: no-op).
    5. **Metrics**: Extract total cost, peak load, and total unmet energy from the solver result.
    6. **Baseline comparison**: Compute uncontrolled (charge-asap) schedule and its cost.
    7. **Explain**: Call `extract_facts` and `generate_explanation` to produce a grounded summary.
  - Returns `AgentResult` with schedule, metrics, feasibility, and explanation.

**How it works**
- The pipeline is modular: each step (plan, optimize, validate, refine, explain) is a separate function call. This makes it easy to extend or replace individual components in future versions.

---

## 3.2 Agent script and visualization

### File: `scripts/run_agent.py`

**Purpose**  
Run the agent from the command line and optionally save the same plots as Phase A.

**What it does**
- **CLI**: `--site` (default `caltech`), `--date` (default yesterday), `--request` (default "Minimize energy cost for this day.").
- **Environment**: Loads `.env` from project root (for `ACN_DATA_API_TOKEN`).

**How it works (step-by-step)**
1. Parse arguments; resolve `day_date`.
2. Call `load_sessions(site_id, day_date)`. On error, print message and exit.
3. If no sessions returned, print message and exit.
4. Build `SiteConfig(P_max_kw=50, n_steps=day.n_steps, dt_hours=day.dt_hours)` and `TOUConfig(rates_per_kwh=default_tou_rates(day.n_steps))` (same as Phase A and baseline).
5. Call `run_agent(day, site, tou, request=args.request)`.
6. Call `check(schedule, day, site)` for independent verification.
7. Compute uncontrolled schedule and cost; call `compute_metrics(...)`.
8. Print: explanation, feasibility, violations (if any, first 10), total cost, peak, total unmet, % fully served, % cost reduction vs uncontrolled.
9. If `experiments/` exists, call `plot_schedule` and `plot_load_profile` and save to `experiments/agent_schedule.png` and `experiments/agent_load.png`.

**Usage**  
From project root with venv active:  
`python -m scripts.run_agent --site caltech --date 2019-06-15`

**Config**  
Uses the same site and TOU config as Phase A and baseline so comparisons are fair.

---

## 3.3 End-to-end data flow (Phase C)

```
.env (ACN_DATA_API_TOKEN)
        │
        ▼
scripts/run_agent.py  ──►  data/loader/loader.py  ──►  DaySessions (list of Session)
        │
        ├── config/site.py  ──►  SiteConfig, TOUConfig (default_tou_rates)
        │
        └── agent/run.py  ──►  run_agent()
                │
                ├── agent/plan/plan.py  ──►  plan()  ──►  PlanResult
                │
                ├── agent/optimize/call_solver.py  ──►  optimize()  ──►  SolveResult
                │       └── optimization/solver.py  ──►  CVXPY solve
                │
                ├── agent/validate/validate.py  ──►  validate()  ──►  CheckResult
                │       └── constraints/checker.py  ──►  check()
                │
                ├── agent/refine/refine.py  ──►  refine()  ──►  (v1: pass-through)
                │
                ├── evaluation/metrics  ──►  charge_asap_schedule(), total_cost()
                │
                └── agent/explain/explain.py  ──►  extract_facts(), generate_explanation()
                        │
                        ▼
                AgentResult (schedule, cost, peak, unmet, feasible, explanation)
                        │
                        ▼
                visualization/plots.py  ──►  experiments/agent_*.png
```

---

# Reference: Midway deliverable checklist

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Data loader, standardized session format, constraint checker | ✅ Done | `data/format/schema.py`, `data/loader/loader.py`, `constraints/checker.py`; loader uses Eve API; checker has violations and tolerance. |
| Prompting baseline implementation and evaluation scripts | ✅ Done | `baseline/prompt.py`, `parse.py`, `run.py`; `scripts/run_baseline.py`; reuses Phase A metrics and checker. |
| Agentic pipeline v1 with optimization solver and visualization | ✅ Done | `agent/plan`, `agent/optimize`, `agent/validate`, `agent/refine`, `agent/explain`, `agent/run.py`; `scripts/run_agent.py`; reuses solver, checker, metrics, and plots from Phase A. |
