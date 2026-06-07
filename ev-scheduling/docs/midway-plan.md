# Midway Deliverables: Step-by-Step Plan (Weeks 4–7)

This plan breaks down the three midway deliverables into ordered steps you can follow. Dependencies between sections are noted so you know what to build first.

---

## 1. Data loader, standardized session format, and constraint checker

**Goal:** Load ACN-Data sessions, represent them in a single format, and verify all constraints.

### 1.1 Standardized session format (`data/format/`)

- [ ] **Define the schema**  
  Per-session fields: arrival time `a_i`, departure time `d_i`, requested energy `E_i` (kWh), assigned charger ID, per-session max power `p̄_i` (and any units/time-step convention). Decide whether you use a single struct/class or a small set of types (e.g. one type per session, one for the full day).

- [ ] **Document the format**  
  In code (docstrings/types) and in `data/format/README.md`: field names, units, time resolution (e.g. 15-min intervals), and how multi-session days are represented (e.g. list of sessions + horizon start/end).

- [ ] **Add serialization if needed**  
  If you want to cache loaded days or feed data to scripts, add a simple way to save/load the standardized format (e.g. JSON or pickle) so the rest of the pipeline does not depend on the API.

### 1.2 Data loader (`data/loader/`)

- [ ] **Wire up ACN-Data access**  
  Use `acnportal.acndata.DataClient` (or the client you have under `acnportal/`) with your ACN-Data API token. Confirm you can fetch sessions for a given site and date.

- [ ] **Map raw API → standardized format**  
  Write a function that takes raw API response(s) for one day and returns one or more “day” objects in your standardized format (all sessions with `a_i`, `d_i`, `E_i`, charger, `p̄_i`, etc.). Handle missing/optional fields and invalid data (e.g. skip or flag bad sessions).

- [ ] **Expose a simple entry point**  
  e.g. `load_sessions(site_id, date)` → standardized day/sessions. Document in `data/loader/README.md` and in the main `README.md` how to set the API token (env var, no secrets in repo).

- [ ] **Optional: small test dataset**  
  Commit a tiny sample (or a script that generates one) so others can run the pipeline without an API key, and so tests are deterministic.

### 1.3 Constraint checker (`constraints/`)

- [ ] **Implement availability**  
  For each session `i`, ensure `p_i(t) = 0` for `t ∉ [a_i, d_i)` (no charging outside arrival–departure window).

- [ ] **Implement per-charger limits**  
  For each session, ensure `0 ≤ p_i(t) ≤ p̄_i` at every time step.

- [ ] **Implement site power cap**  
  Ensure `∑_i p_i(t) ≤ P_max(t)` at every `t` (use config for `P_max` if it varies by time).

- [ ] **Implement energy delivery**  
  Ensure `∑_t p_i(t)∆ + u_i = E_i` with `u_i ≥ 0` (slack `u_i` = unmet energy). Decide time step `∆` and units (e.g. kW and hours) and document them.

- [ ] **Single entry point**  
  One function (or small API) that takes a schedule (and session list + site config) and returns: feasible yes/no, list of violations, and optionally per-session unmet energy and peak load. Used by baseline (optional repair) and agent (Validate step).

- [ ] **Unit tests**  
  Tests with hand-crafted schedules: one that satisfies all constraints, and several that violate each constraint type, to ensure the checker flags them correctly.

---

## 2. Prompting baseline implementation and evaluation scripts

**Goal:** A single-shot LLM baseline that outputs a charging schedule, plus scripts to evaluate it.

### 2.1 Baseline implementation (`baseline/`)

- [ ] **Define inputs and outputs**  
  Inputs: facility constraints (site cap, TOU rates, horizon), session data in standardized format. Output: a charging schedule in the same shape your constraint checker expects (e.g. `p_i(t)` per session per time step).

- [ ] **Build the prompt**  
  Assemble a prompt that describes the objective (minimize TOU cost), horizon, constraints, and session parameters (arrival, departure, requested energy, charger, max power). Use clear structure (e.g. bullet list or table) so the LLM can produce a parseable schedule.

- [ ] **Parse LLM output**  
  Convert the model’s text (or structured output) into the schedule format (e.g. matrix or list of (session, time, power)). Handle parsing failures gracefully (return error or partial result and flag it).

- [ ] **Optional: repair step**  
  If the schedule violates constraints, run one projection/repair step (e.g. clip to [a_i,d_i], clip to `p̄_i`, scale to meet site cap, then recompute unmet energy). Document whether metrics are reported before and/or after repair.

- [ ] **Single entry point**  
  e.g. `run_baseline(sessions, config)` → schedule (and optionally raw response, parse success, etc.). Keep API key in env; no hardcoded secrets.

### 2.2 Evaluation scripts (`evaluation/`, `scripts/`)

- [ ] **Cost and feasibility metrics**  
  Implement: total energy cost ($), total unmet energy, % EVs fully served, constraint violation count. Use your constraint checker and a shared TOU cost function so baseline and agent use the same definitions.

- [ ] **Peak load**  
  Compute `max_t ∑_i p_i(t)` and report it (for comparison and for later faithfulness checks).

- [ ] **Uncontrolled baseline**  
  Implement “charge-asap” (or simple heuristic): each EV charges at max rate from arrival until energy is met. Compute its cost and peak so you can report % cost reduction vs uncontrolled.

- [ ] **Evaluation script for baseline**  
  Script that: loads one or more days (via data loader), runs the baseline, runs the constraint checker, computes cost/unmet/peak/violations and (if you have it) cost vs uncontrolled. Output: JSON or table (e.g. CSV) with metrics per run/day.

- [ ] **Reproducibility**  
  Document: which model, which prompt version, and how to run the evaluation script (e.g. in `scripts/README.md` or main `README.md`).

---

## 3. Agentic pipeline v1 with optimization solver and visualization

**Goal:** First version of the agent pipeline (Plan → Optimize → Validate → Refine → Explain) plus optimization and plots.

### 3.1 Optimization solver (`optimization/`)

- [ ] **Decision variables and parameters**  
  Implement in CVXPY: `p_i(t)` (kW) per session per time step, time step `∆`, and slack `u_i` for unmet energy. Load TOU vector `c(t)` and site/session params from config.

- [ ] **Objective**  
  Minimize `∑_t c(t) ∑_i p_i(t)∆ + M ∑_i u_i` (energy cost + penalty for unmet). Report `max_t ∑_i p_i(t)` after solving. Use the same units and horizon as the rest of the project.

- [ ] **Constraints**  
  Add constraints that mirror the constraint checker: availability, per-charger limits, site cap, and energy delivery with slack. Ensure the solver’s formulation and the checker’s checks use the same conventions.

- [ ] **API for the agent**  
  Single function (e.g. `solve(sessions, site_config, tou_rates)`) that returns the schedule, cost, unmet energy, and peak load. Handle infeasibility (e.g. return status + partial result or clear error).

- [ ] **Tests**  
  At least one test: small instance with known solution or known feasibility; compare solver output to constraint checker.

### 3.2 Agentic pipeline v1 (`agent/`)

- [ ] **Plan**  
  Parse user request (or a fixed “minimize cost for this day” request) into: objective, horizon, constraints, session parameters. Output a structured representation (e.g. dict or config object) that the optimizer and checker understand.

- [ ] **Optimize**  
  Call the optimization module with the planned params; pass through schedule, cost, peak, unmet.

- [ ] **Validate**  
  Run the constraint checker on the optimizer’s schedule. If violations appear (e.g. due to numerical tolerance), decide whether to treat as success or trigger Refine.

- [ ] **Refine**  
  On parsing or implementation errors (e.g. infeasible, bad params), fix the structured representation and re-run Optimize (and optionally Validate). Define a simple policy (e.g. max one retry, or retry only on certain errors) so v1 doesn’t loop forever.

- [ ] **Explain**  
  From the computed schedule and metrics, extract concrete facts (total cost, savings vs uncontrolled, peak load, unmet energy). Generate a short natural-language explanation that uses only these facts (grounded). Store or return both schedule and explanation.

- [ ] **End-to-end entry point**  
  One function or script that runs Plan → Optimize → Validate → Refine (if needed) → Explain for a given day/sessions and returns schedule + metrics + explanation.

### 3.3 Visualization (`visualization/`)

- [ ] **Schedule matrix**  
  Plot `p_i(t)` (e.g. sessions vs time, color = power). Label axes and include a legend or colorbar. Save to file (e.g. PNG) for reports.

- [ ] **Facility load profile**  
  Plot `∑_i p_i(t)` vs time. Optionally annotate with TOU periods or cost/unmet summary (e.g. in title or text box).

- [ ] **Integration**  
  Accept the same schedule format the optimizer and checker use. Provide a simple API (e.g. `plot_schedule(schedule, sessions, path)` and `plot_load_profile(schedule, sessions, path)`). Document in `visualization/README.md`.

### 3.4 Tie it together

- [ ] **Script to run agent v1**  
  In `scripts/`: load a day (data loader), run the full agent pipeline, run constraint checker and cost computation, then generate visualizations. Output metrics (and optionally explanation) to console or file.

- [ ] **Consistent config**  
  Use `config/` for site constraints, TOU rates, and any experiment settings so baseline and agent share the same numbers and so evaluation is reproducible.

---

## Suggested order of work

1. **Format → Loader → Checker**  
   Do 1.1 (format) first, then 1.2 (loader), then 1.3 (checker). The checker is needed for both baseline and agent.

2. **Optimization early**  
   Implement 3.1 (optimization) as soon as the format and checker exist. It gives you a “ground truth” feasible schedule and clarifies units and conventions.

3. **Baseline and evaluation**  
   Do 2.1 and 2.2 in parallel or right after the checker; you need the evaluation scripts to compare baseline vs agent.

4. **Agent pipeline then visualization**  
   Build 3.2 (agent) using the optimizer and checker; then add 3.3 (visualization) and 3.4 (scripts) so you can run and inspect full days.

---

## Checklist summary

| Deliverable | Key artifacts |
|-------------|----------------|
| **Data + format + checker** | `data/format/` schema & docs, `data/loader/` ACN-Data → format, `constraints/` checker with tests |
| **Baseline + evaluation** | `baseline/` prompt + parse + optional repair, `evaluation/` metrics, `scripts/` run & eval baseline |
| **Agent v1 + optimization + viz** | `optimization/` CVXPY solver, `agent/` Plan→Optimize→Validate→Refine→Explain, `visualization/` schedule + load plots, `scripts/` run agent |

Good luck with the midway deliverables.
