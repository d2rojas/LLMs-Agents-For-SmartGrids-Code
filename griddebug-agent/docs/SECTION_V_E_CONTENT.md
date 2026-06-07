# Section V.E Content: GridDebugAgent
## Content Guide for Main Paper

This document extracts all necessary content from the student's implementation and report for incorporating GridDebugAgent into Section V.E of the main paper.

---

## A. Problem Description

### Problem Setup (from student report)

**Task:** Power flow failure diagnosis and repair

**Formal Definition:**
- **Input:** Power network state `N` (buses, lines, generators, loads) with simulation failure
- **Output:** Diagnostic report with:
  - Root causes (initiating events)
  - Affected components (buses/lines with violations)
  - Corrective actions (feasible remediation steps)
  - Optional: Repaired network state `N'` with zero violations

**Failure Types:**
1. **Non-convergence:** Load flow solver fails to converge
2. **Voltage violations:** Bus voltages outside [0.95, 1.05] p.u.
3. **Thermal overloads:** Line/transformer loading > 100%

**Challenge:** Grid operators need to:
- Quickly diagnose root causes in complex failures
- Understand cascading effects (e.g., line outage → voltage violations)
- Identify minimal corrective actions without manual trial-and-error

**Why LLM agents?**
- Complex reasoning over network topology
- Multi-step diagnostic workflows
- Tool orchestration for simulation and repair
- Natural language reporting for operators

---

## B. Methodology

### System Architecture (refer to figure)

GridDebugAgent implements a **solver-grounded ReAct architecture** where all numerical results come from trusted simulation tools (pandapower).

**Components:** (See `Figure X: griddebug_architecture.tex`)

1. **Preprocessing Pipeline**
   - Evidence Collector: Extracts metrics (convergence, voltages, loading, power balance)
   - Rule Engine: Classifies failure type and triggers diagnostic rules
   - Context Builder: Formats evidence for LLM prompt

2. **Agent Core** (ReAct Loop)
   - LLM: GPT-4o, temperature 0.3, max 2000 tokens
   - Max iterations: 10 tool calls
   - Tool selection: OpenAI function calling
   - Execution: Direct calls to pandapower via tools

3. **Tool Suite** (23 tools across 4 categories)
   - **Query (9):** Network inspection (get_network_summary, get_voltage_profile, get_power_balance, etc.)
   - **Simulation (7):** Power flow analysis (run_power_flow, run_n1_contingency, run_opf, etc.)
   - **Diagnostic (4):** Violation detection (check_overloads, check_voltage_violations, etc.)
   - **Grid Actions (4):** Remediation (adjust_generation, curtail_load, switch_line, switch_shunt)

4. **Memory Management**
   - Network snapshots: Save/restore network state
   - Conversation history: Full message log for reproducibility
   - Tool call logs: Audit trail of all tool invocations

### Prompt Design

**System Prompt Structure:**
```
You are GridDebugAgent Level 2, an expert power systems engineer...

## Analysis & Iterative Debugging Strategy
1. Read user query and triggered rules
2. For NON-CONVERGENCE: Focus on load/gen balance
3. For VOLTAGE VIOLATIONS: Use get_voltage_profile, trace to root cause
4. For THERMAL OVERLOADS: Use get_loading_profile, check contingencies
5. ITERATIVE DEBUGGING: Propose→Act→Verify loop
6. Use tools STRATEGICALLY

## Available Tools
[List of 23 tools with descriptions]

## Output Requirements
FINAL REPORT:
- Root Causes (initiating events, not symptoms)
- Affected Components (buses/lines with violations)
- Corrective Actions (minimal, engineering-feasible)
- Reasoning Trace (tool findings and analysis)
```

**User Prompt Components:**
- Network name (e.g., IEEE-14)
- Failure category (from rule engine)
- Optional user query
- Evidence text (metrics, violations)
- Triggered rules (severity, descriptions, suggested actions)
- Network summary (bus/line/gen counts)

### Baselines

**Baseline 1: Single-pass LLM** (no tools, no iteration)
- Direct GPT-4o call with evidence
- No ability to gather additional information
- No ability to execute repairs

**Baseline 2: Agentic Pipeline** (with tools, ReAct loop)
- Full tool access
- Iterative diagnosis and repair
- **This is GridDebugAgent**

---

## C. Evaluation Setup

### Test Networks
- **IEEE 14-bus:** 14 buses, 20 lines, 5 generators, 11 loads
- **IEEE 30-bus:** 30 buses, 41 lines, 6 generators, 20 loads
- **IEEE 57-bus:** 57 buses, 80 lines, 7 generators, 42 loads

### Failure Scenarios (39 total)
- **Category 1:** Line outages (N-1 contingencies)
- **Category 2:** Load/generation imbalances
- **Category 3:** Equipment failures (generator/transformer out)
- **Category 4:** Parameter violations (extreme loads)

All scenarios hand-crafted to produce realistic constraint violations.

### Metrics

1. **Repair Rate (%):** Fraction of scenarios where agent achieves zero violations
2. **Violation Reduction:** (initial_violations - final_violations) / initial_violations
3. **Feasibility:** Whether corrective actions are engineering-realistic
4. **Tool Calls:** Average number of tool invocations per scenario
5. **Latency:** Time per scenario (seconds)

### Evaluation Protocol
- Run agent on each scenario
- Check if repaired network converges
- Check if all voltage/thermal violations resolved
- Verify actions are feasible (no impossible adjustments)
- Log tool calls and conversation

---

## D. Results

### Main Results (from `backend/eval/results/README.md`)

**Overall Performance:**
- **Repair Rate:** 84.6% (33/39 scenarios)
- **Violation Reduction:** 497 → 237 violations (52.3% reduction)
- **Avg Tool Calls:** 22.5 per scenario
- **Avg Latency:** ~15-30 seconds per scenario

**By Network Size:**

| Network | Scenarios | Repair Rate | Violations (before→after) | Avg Tool Calls |
|---------|-----------|-------------|---------------------------|----------------|
| IEEE-14 | 13        | **100%** (13/13) | 48 → 1 | 12.7 |
| IEEE-30 | 13        | **92.3%** (12/13) | 128 → 44 | 20.6 |
| IEEE-57 | 13        | **61.5%** (8/13) | 321 → 192 | 34.4 |

**Key Findings:**
1. **Scalability challenge:** Repair rate degrades with network size (100% → 61.5%)
2. **Tool usage increases:** Larger networks require more tool calls (12.7 → 34.4)
3. **Partial success:** Even failed repairs often reduce violations significantly
4. **Perfect small networks:** 100% repair on IEEE-14 shows strong diagnostic reasoning

### Failure Analysis

**Common failure modes on IEEE-57:**
- **Max iterations reached** (10 tool calls insufficient)
- **Suboptimal action selection** (adjusts wrong generators)
- **Cascading effects** (fixing one violation creates another)
- **Convergence issues** (some combinations don't converge)

**Success patterns:**
- **Simple contingencies** (single line outage) → high success
- **Clear root causes** (load/gen imbalance) → high success
- **Multiple interacting failures** → lower success

### Comparison to Baseline (from student report)

**Baseline (Single-pass, no tools):**
- Repair Rate: 0% (cannot execute actions)
- Can identify problems but not fix them
- Outputs generic advice ("increase generation")

**Agentic Pipeline (GridDebugAgent):**
- Repair Rate: 84.6%
- Takes specific, grounded actions
- Verifies fixes with power flow

**Key advantage:** Tool access + iteration enables actual repair, not just diagnosis.

---

## E. Example Trajectory

**Figure:** `griddebug_trajectory.tex` in docs folder

**Iterative Repair Loop (IEEE-14, Line Outage)**

**User:** Disconnect line 2-3 and report any voltage violations or overloads.

**Round 1 (Diagnosis):**
- Tools: save_network_snapshot → switch_line(2, false) → run_power_flow → check_voltage_violations
- Result: Over-voltage at buses 5 (1.07 pu) and 7 (1.09 pu)

**Round 2 (Repair):**
- Reasoning: Reduce generator voltage setpoints to fix over-voltage
- Tools: adjust_generation(gen=0, vm_pu=1.05) → adjust_generation(gen=1, vm_pu=1.05) → run_power_flow → check_voltage_violations
- Result: All violations eliminated ✓

**Final Report:** "Network repaired. Line 2-3 outage caused over-voltage at buses 5 and 7. Reducing generator setpoints to 1.05 pu eliminated all violations."

**Key observations:**
- Agent identifies root cause (line outage)
- Selects appropriate corrective action (adjust generators)
- Verifies fix with simulation
- Produces natural language report

---

## F. Discussion Points

### Strengths
1. **Solver-grounded:** All numbers from trusted tools (no hallucination)
2. **Iterative repair:** ReAct loop enables diagnose→act→verify workflow
3. **Tool orchestration:** Effectively combines 23 tools for complex tasks
4. **Interpretable:** Full tool logs and reasoning traces
5. **Practical actions:** Generates engineering-feasible corrections

### Limitations
1. **Scalability:** Performance degrades on larger networks (57-bus)
2. **Fixed iteration limit:** 10 tool calls may be insufficient
3. **No lookahead:** Greedy action selection, no planning
4. **Convergence sensitivity:** Some action combinations don't converge
5. **No cost awareness:** Doesn't optimize for minimal interventions

### Future Work
- **Hierarchical planning:** Decompose large networks into manageable subproblems
- **Learned action priors:** Fine-tune tool selection for power systems
- **Adaptive iteration budget:** Dynamically adjust max tool calls
- **Multi-objective optimization:** Balance violation reduction vs. action cost
- **Real-time deployment:** Optimize latency for control room use

---

## G. LaTeX Figures to Include

1. **Figure X:** `griddebug_architecture.tex` - System architecture
   - Caption: "GridDebugAgent architecture with preprocessing, ReAct loop, 23 tools, and memory management"
   - Label: `\label{fig:griddebug_architecture}`

2. **Figure Y:** `griddebug_trajectory.tex` - Iterative repair trajectory
   - Caption: "GridDebugAgent demonstrating diagnose-act-verify ReAct loop with line outage contingency"
   - Label: `\label{fig:griddebug_trajectory}`

3. **Table VIII:** Results by network size (create in paper)
   - Columns: Network | Scenarios | Repair Rate | Violations (before→after) | Avg Tool Calls
   - Data: See section D above

---

## H. Key Citations Needed

From student report, they cite:
- Yao et al. (2023) - ReAct: Reasoning + Acting in LLMs
- Pandapower library - Thurner et al. (2018)
- IEEE test systems - Power Systems Test Case Archive
- GPT-4o - OpenAI (2024)

---

## I. Integration Checklist

For adding to main paper Section V.E:

- [ ] Add architecture diagram (`griddebug_architecture.tex`)
- [ ] Add trajectory figure (`griddebug_trajectory.tex`)
- [ ] Create results table (Table VIII) from section D
- [ ] Write problem description (section A)
- [ ] Write methodology subsection (section B)
- [ ] Write results subsection (section D)
- [ ] Add discussion of limitations (section F)
- [ ] Update main paper references
- [ ] Cross-reference figures in text
- [ ] Ensure consistent terminology with rest of paper

---

## J. Quick Summary for Abstract/Intro

If you need to reference GridDebugAgent in the paper's introduction:

> "We implement GridDebugAgent, a ReAct-style agentic system for power flow
> failure diagnosis and remediation. The system orchestrates 23 tools across
> query, simulation, diagnostic, and action categories to iteratively diagnose
> and repair constraint violations. Evaluated on 39 failure scenarios across
> IEEE test networks, GridDebugAgent achieves 84.6% repair rate overall, with
> 100% success on smaller networks but degraded performance on larger systems,
> highlighting scalability challenges for agentic power systems applications."

---

## File Locations

- **Figures:** `/docs/griddebug_architecture.tex`, `/docs/griddebug_trajectory.tex`
- **Source data:** `backend/eval/results/README.md`, `backend/eval/results/*.json`
- **Student report:** `final report.pdf`
- **Implementation:** `backend/agents/agentic_pipeline.py`, `backend/tools/*.py`
