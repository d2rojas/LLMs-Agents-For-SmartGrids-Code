# EV Scheduling Benchmark Matrix

model=openrouter:openai/gpt-4o-mini resolved=openai/gpt-4o-mini  
days=20 seeds=[0] repeats=1 items/arm=20  
data_source=cache synthetic=False requests_digest=sha256:77e41af52a48db623768923f0b30c79966638643baf21b68db26b990da867967  
budget_ceiling_usd=0.3 spent_usd=0.0752 traceability_policy=grounded_only  

| arm | items | failed | Solved | Escalated | Wrong unflagged | Form. | Form. days | FR | Traceable | Answer | gap % | cost $ | repaired | USD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| evagent | 20 | 0 | 0.0% (0/20) | 100.0% (20/20) | 0.0% (0/20) | 90.2% (806/894) | 0.0% (0/20) | 100.0% (20/20) | 95.0% (19/20) | 31.6% (6/19) | -100.00 | 0.00 | n/a (0/0) | 0.0752 |

Every rate carries its denominator. `n/a (0/0)` means the term was not measured for that arm, which is not the same as passing: `Form.` needs an extraction step, `Traceable` needs a tool output for the numbers to trace to, and `Escalated` needs a gate.

`Form.` is per session, over ground-truth sessions, which is what the supplement's Table S3 defines. `Form. days` is the day verdict: a day counts only when every one of its sessions is exact, so it is near zero on days with dozens of cars and is printed next to the per-session rate rather than in place of it.

`Solved` is the conjunction of the state check, traceability, the answer check and the gate. Formulation is not one of its terms, so a wrong formulation is visible in `Form.` alone. It usually still costs the day its `Solved`, through the state check: a schedule optimised on misread parameters breaks the real session's constraint.

`failed` counts rows the arm did not complete. They are written to the rows files with their error and are excluded from every rate above, so a rate must always be read next to it.
