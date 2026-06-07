# Questions for Students - Embedded in LaTeX

These questions have been added as comments in `section_5b_hybrid.tex` to flag critical discrepancies between the report claims and actual implementation.

---

## QUESTION 1 - About the "5-Step Loop" (Line 31)

**Location:** Before the "3 stages" description in the Method section

**LaTeX Comment:**
```latex
% QUESTION 1 FOR STUDENTS: Your report describes a "5-step ReAct loop: Parse → Plan → Optimize →
% Validate → Refine → Explain". However, the code shows Plan (agent/plan/plan.py:34-63) and
% Refine (agent/refine/refine.py:17-43) are pass-throughs with no logic (comments say "v1:
% pass-through, no refinement logic"). Why does the report claim 5 steps when only 3 are implemented?
% Was this initial design that wasn't finished, or a misunderstanding of what was built?
```

**Code Evidence:**

`agent/plan/plan.py:34-63`:
```python
def plan(request, day, site, tou):
    """For v1, this is a simple pass-through: the request string is stored in `raw`
    but not parsed. The objective is always "minimize_cost"."""
    return PlanResult(day=day, site=site, tou=tou, objective="minimize_cost", raw=request)
```

`agent/refine/refine.py:17-43`:
```python
def refine(day, site, tou, solve_result, max_retries=1):
    """For v1, this is a simple pass-through: the inputs and solve_result are
    returned unchanged."""
    # v1: pass-through, no refinement logic
    return (day, site, tou, solve_result)
```

**What to ask:**
- Why claim "5-step ReAct loop" when only Parse, Optimize, and Explain work?
- Were Plan and Refine intended to be implemented but ran out of time?
- Did you understand what these steps should do?

---

## QUESTION 2 - About Validation Not in Loop (Line 47)

**Location:** After the "Explain" stage description

**LaTeX Comment:**
```latex
% QUESTION 2 FOR STUDENTS: Your report states "Validate (checker): any flags are surfaced to the
% agent" and "Refine (GPT-4o): corrects and retries". However, validate() is called on line 395
% of agent/llm_agent.py, AFTER the agent loop exits (lines 332-376). The validation results are
% NOT added to messages[], NOT seen by the LLM, and NOT used for self-correction. Why does the
% report claim validation is part of the agent loop when it's actually post-processing? Was
% validation intended to be in the loop originally? If so, what prevented implementation?
```

**Code Evidence:**

`agent/llm_agent.py:332-376` - The agent loop:
```python
while tool_rounds < max_tool_rounds:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=[_SOLVE_TOOL],
        tool_choice="auto",
    )
    # ... tool execution ...
    messages.append({
        "role": "tool",
        "content": json.dumps(tool_result),  # ← Only solver metrics, NO checker!
    })
    # Loop ends here
```

`agent/llm_agent.py:395` - AFTER loop exits:
```python
check_result = validate(schedule, day, site)  # ← Post-processing
feasible = check_result.feasible
return schedule, ..., feasible, explanation
```

**What to ask:**
- Why does the report say "flags are surfaced to the agent" when they're not?
- Was validation intended to be in the loop with feedback to the LLM?
- If yes, what prevented you from implementing it?
- Do you understand the difference between post-hoc validation and in-loop validation?

---

## How to Use These Questions

### In Person Discussion:
1. Open the LaTeX file and show them the comments
2. Walk through the code files referenced
3. Ask them to explain the discrepancy
4. Assess whether it was:
   - Time constraints (ran out of time to implement)
   - Design misunderstanding (didn't know what ReAct/validation means)
   - Intentional overselling (knew it wasn't implemented but claimed it anyway)

### In Written Feedback:
The comments are already embedded in the LaTeX. Students will see them when they open the file. You can reference:
> "See QUESTION 1 and QUESTION 2 in the LaTeX comments of section_5b_hybrid.tex for critical issues that need addressing."

---

## Expected Responses & Follow-ups

### If they say "We ran out of time":
**Follow-up:** "Then the report should say '3-stage pipeline' not '5-step loop'. Can you revise the report to reflect what was actually implemented?"

### If they say "Plan and Refine were placeholders for future work":
**Follow-up:** "The report presents them as completed features, not future work. This is misleading. Can you clarify in the report which features are implemented vs planned?"

### If they say "Validation was too hard to put in the loop":
**Follow-up:** "That's fine, but why does the report claim 'flags are surfaced to the agent'? This implies the agent uses validation for self-correction, which doesn't happen."

### If they seem confused about what they built:
**Follow-up:** "Can you demonstrate the system working? Show me where in the code the agent actually does each of the 5 claimed steps."

---

## Summary

**Two critical discrepancies flagged:**
1. ❌ **5 steps claimed, only 3 implemented** (Plan and Refine are empty)
2. ❌ **Validation claimed to be in agent loop, actually post-processing** (no feedback to LLM)

**Both indicate either:**
- Incomplete work presented as complete
- Misunderstanding of what was built
- Borrowing descriptions from papers without verification

**Action required:** Students must either:
- Implement the missing features, OR
- Revise report to accurately describe the 3-stage architecture actually built
