# Questions and Action Items for Student Team

## 🔴 CRITICAL - Security Issue

### ⚠️ API Key Exposure
**Issue:** The `.env` file contains an exposed OpenAI API key:
```
OPENAI_API_KEY=***REMOVED***...
```

**Action Required:**
1. **IMMEDIATELY revoke this API key** in your OpenAI account
2. Generate a new key
3. Verify the key was never pushed to git history: `git log --all --full-history -- "*/.env"`
4. If it was in git history, consider the key permanently compromised
5. Create `.env.example` template:
   ```bash
   OPENAI_API_KEY=sk-proj-your-key-here
   ```

✅ Good news: `.gitignore` correctly excludes `.env`, and `git ls-files` shows it's not currently tracked.

---

## 📊 Evaluation & Results Questions

### 1. Baseline Implementation ✅ **CONFIRMED**
**Status:** Baseline IS evaluated and documented in `backend/eval/results/README.md`!

**What's documented:**
- Line 54: Baseline results showing 1 tool call, 3.8s avg latency
- Lines 76-97: Detailed baseline component detection (Precision, Recall, F1)
- Baseline is "single-pass diagnosis only, no remediation"

**Clarification needed:**
- [ ] Baseline shows "N/A" for Repair/Feasibility/Violations - confirm this is expected (diagnosis-only, can't repair)
- [ ] Should paper emphasize that baseline can diagnose but NOT repair?

**Overall:** Baseline is well-evaluated! Just need to clarify the N/A metrics.

### 2. Missing Ablation Studies
**From your report TODOs, these analyses are marked as future work:**
- Tool-category ablation (Query only, Simulation only, etc.)
- Cascading failure rate analysis
- Repair rate vs. tool-call budget curve

**Question:** Should we mention these as "planned" or remove references?

### 3. Evaluation Reproducibility
**Question:** Can we re-run your evaluations to verify results?

**Please confirm:**
- [ ] `python backend/eval/run_eval.py` reproduces your results?
- [ ] Any random seeds set for reproducibility?
- [ ] Expected runtime? (API costs?)
- [ ] Are the 39 scenarios deterministic or randomly generated?

**What we found:**
✅ Evaluation scripts exist: `run_eval.py`, `generate_figures.py`
✅ Results are in JSON: `full_eval_case14.json`, etc.
✅ README.md documents metrics

---

## 📝 Documentation Gaps

### 4. Scenario Definitions ✅ **DOCUMENTED**
**Status:** The 39 scenarios ARE well-documented in `backend/eval/results/README.md`!

**What's documented:**
- 13 scenarios per network (repeated across IEEE 14/30/57-bus)
- Categories: 1 normal, 4 non-convergence, 3 voltage, 3 thermal, 2 contingency
- Scenario names: `normal_operation`, `extreme_load_scaling`, `all_generators_removed`, etc.
- Complete results table with violations, ReAct iterations, tool calls, latency, success

**Great documentation!** No action needed here.

### 5. Tool Usage Statistics
**Question:** Which tools are used most frequently?

**What we found:**
- Tool call logs in JSON results
- Average tool calls per network size
- But no breakdown by tool type

**Would be interesting for paper:**
- Top 5 most-used tools
- Query vs. Simulation vs. Diagnostic vs. Action tool usage ratios
- Does tool usage pattern differ by network size?

**Can you extract this from your logs?**

---

## 🔧 Technical Clarifications

### 6. Max Iterations = 10
**Question:** Why 10? Was this tuned experimentally?

**Context:**
- IEEE-57 failures often cite "max iterations reached"
- Average tool calls: 12.7 (14-bus), 20.6 (30-bus), 34.4 (57-bus)

**For paper:**
- [ ] Should we mention you tried other limits?
- [ ] Or just state "we set max=10 based on computational budget"?

### 7. Voltage Limits Discrepancy ⚠️ **NEEDS FIX**
**Issue:** Your eval README says 0.95-1.05 p.u., but trajectory example uses 0.95-1.06 p.u.

**From eval/results/README.md line 12:**
> Voltage limits | 0.95-1.05 p.u.

**In our trajectory figure:**
> check_voltage_violations(v_min=0.95, v_max=1.06)

**Action needed:**
- [ ] We should update trajectory to use v_max=1.05 (not 1.06) to match your evaluations
- [ ] Or clarify if different limits are used for different scenarios

**This is minor but should be consistent.**

### 8. Repair Success Definition
**Question:** What counts as "repaired"?

**Assumed definition:**
- Zero voltage violations (within limits)
- Zero thermal overloads (<100% loading)
- Power flow converges

**Confirm:**
- [ ] Is this correct?
- [ ] Or do you allow small residual violations?
- [ ] What about partial repairs (e.g., 50% violation reduction)?

---

## 🎯 Paper Integration Questions

### 9. Student Names & Affiliations
**Question:** How should we credit your work in the paper?

**Need from you:**
- [ ] Student names (full names for citation)
- [ ] Course/project affiliation (e.g., "CSE 599: LLMs for Power Systems, University of...")
- [ ] Preferred citation format
- [ ] Permission to use your figures/results

**Current phrasing in section:**
> "We implement GridDebugAgent..."

**Should we say:**
> "Students X, Y, Z implemented GridDebugAgent as part of..."?

### 10. Code Availability
**Question:** Will the code be publicly available?

**For paper reproducibility:**
- [ ] GitHub repository URL?
- [ ] License? (MIT, Apache, etc.)
- [ ] Data availability statement?

**If not public:**
- We can say "Implementation available upon request"

---

## 🐛 Potential Issues to Verify

### 11. Tool Count Discrepancy
**In your README:**
> Query: 4 tools, Simulation: 3 tools, Diagnostic: 3 tools

**In your actual code (TOOL_DEFINITIONS):**
- Query: 9 tools
- Simulation: 7 tools
- Diagnostic: 4 tools
- Grid Actions: 4 tools
**Total: 23 tools**

**Which is correct?**
- [ ] Update README to match code? (we used 23 tools in the paper section)

### 12. Temperature Setting
**Question:** Why temperature = 0.3?

**Context:**
- Lower than typical 0.7 for creative tasks
- But not deterministic (temp=0)

**For paper:**
- [ ] Was this tuned experimentally?
- [ ] Or standard practice for tool-calling tasks?

### 13. Missing Grid Action Tools in README
**Your README lists:**
- Query, Simulation, Diagnostic tools

**But code has a 4th category:**
- Grid Action tools: `adjust_generation`, `curtail_load`, `switch_line`, `switch_shunt`

**These are critical for repair!**
- [ ] Please update README to include Grid Actions category

---

## 📈 Results Validation

### 14. Violation Counts
**Your reported results:**
- IEEE-14: 48 → 1 violations
- IEEE-30: 128 → 44 violations
- IEEE-57: 321 → 192 violations

**Questions:**
- [ ] Why 1 residual violation on IEEE-14 if repair rate is 100%?
  - Is this from a scenario that was already "healthy" but had 1 violation?
  - Or is "repair" defined differently?

- [ ] IEEE-30: 44 residual violations across 13 scenarios
  - Average ~3.4 violations per scenario
  - But 12/13 repaired (92.3%)
  - So 1 scenario has all 44 violations?

**Please clarify the distribution of violations across scenarios**

### 15. Latency Numbers ✅ **DOCUMENTED**
**Status:** Detailed latency statistics are in `eval/results/README.md` lines 158-164!

**What's documented:**
- IEEE 14-bus: 83.0s avg (range 11.7–188.0s)
- IEEE 30-bus: 177.2s avg (range 11.1–574.0s)
- IEEE 57-bus: 236.3s avg (range 114.8–458.1s)
- Overall agentic: 165.5s avg
- Baseline: 3.8s avg

**For paper:**
- Original estimate of "15-30s" was too optimistic
- Should we use the actual numbers (83s, 177s, 236s) instead?
- Or keep high-level and say "83-236 seconds depending on network size"?

---

## ✅ What's Working Great (No Questions)

These things look excellent in your implementation:

✅ **Clean code structure** - well-organized tools, agents, scenarios
✅ **Comprehensive tooling** - 23 tools covering all aspects
✅ **Solver-grounded approach** - all results from pandapower
✅ **Memory management** - network snapshots implemented
✅ **Full evaluation** - 39 scenarios, complete JSON logs
✅ **Visualization** - React Flow frontend
✅ **Documentation** - good README, eval results documented
✅ **Security** - .env properly gitignored

**Great work overall!** These questions are mostly for paper completeness and clarification.

---

## 📋 Summary Checklist

**Critical (Do ASAP):**
- [ ] Revoke exposed API key
- [ ] Create `.env.example` template

**For Paper Completeness:**
- [ ] Clarify baseline evaluation status
- [ ] Document 39 scenarios (table or appendix)
- [ ] Confirm voltage limits used (0.95-1.05 vs 0.95-1.06)
- [ ] Provide student names and affiliations
- [ ] Confirm code availability (public/private)

**Nice to Have:**
- [ ] Tool usage breakdown statistics
- [ ] Violation distribution by scenario
- [ ] Rationale for hyperparameters (temp=0.3, max_iter=10)
- [ ] Update README (23 tools, Grid Actions category)
- [ ] Latency breakdown by network size

---

## 📞 How to Respond

Please reply with:

1. **Immediate actions taken** (API key revocation)
2. **Answers to numbered questions** (or note which ones are N/A)
3. **Any corrections** to our paper section content
4. **Additional context** we should include

We've drafted a complete Section V.E for the paper based on your excellent implementation. These questions will help us ensure accuracy and completeness.

Thank you for the great work on GridDebugAgent! 🚀
