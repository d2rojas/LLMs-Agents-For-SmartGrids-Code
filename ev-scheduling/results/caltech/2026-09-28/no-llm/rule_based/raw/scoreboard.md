# EV Scheduling Benchmark Matrix

model=openrouter:openai/gpt-4o-mini resolved=openai/gpt-4o-mini  
days=20 seeds=[0] repeats=1 items/arm=20  
data_source=cache synthetic=False requests_digest=sha256:77e41af52a48db623768923f0b30c79966638643baf21b68db26b990da867967  
budget_ceiling_usd=0.75 spent_usd=0.2859 traceability_policy=grounded_only  

| arm | items | failed | Solved | Escalated | Wrong unflagged | Form. | Form. days | FR | Traceable | Answer | gap % | cost $ | repaired | USD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rule_based | 20 | 0 | 90.0% (18/20) | 0.0% (0/20) | 10.0% (2/20) | 100.0% (894/894) | 100.0% (20/20) | 100.0% (20/20) | n/a (0/0) | 89.5% (17/19) | -0.00 | 100.83 | n/a (0/0) | 0.0000 |
| llm_only:structured | 20 | 0 | 0.0% (0/20) | 0.0% (0/20) | 100.0% (20/20) | 91.9% (822/894) | 0.0% (0/20) | 5.0% (1/20) | n/a (0/0) | 15.8% (3/19) | 355.12 | 447.86 | 0.0% (0/20) | 0.0512 |
| llm_only:chain_of_thought | 20 | 0 | 0.0% (0/20) | 0.0% (0/20) | 100.0% (20/20) | 92.1% (743/807) | 5.3% (1/19) | 5.0% (1/20) | n/a (0/0) | 5.3% (1/19) | 314.68 | 401.15 | 5.0% (1/20) | 0.0708 |
| plan_act | 20 | 0 | 0.0% (0/20) | 0.0% (0/20) | 100.0% (20/20) | 90.2% (806/894) | 0.0% (0/20) | 5.0% (1/20) | 100.0% (20/20) | 36.8% (7/19) | -0.00 | 100.73 | n/a (0/0) | 0.0525 |
| react | 20 | 0 | 0.0% (0/20) | 0.0% (0/20) | 100.0% (20/20) | 90.6% (810/894) | 0.0% (0/20) | 5.0% (1/20) | 100.0% (20/20) | 31.6% (6/19) | -0.04 | 100.71 | n/a (0/0) | 0.0557 |
| evagent | 20 | 0 | 0.0% (0/20) | 0.0% (0/20) | 100.0% (20/20) | 90.5% (809/894) | 0.0% (0/20) | 5.0% (1/20) | 100.0% (20/20) | 31.6% (6/19) | -0.04 | 100.70 | n/a (0/0) | 0.0557 |

Every rate carries its denominator. `n/a (0/0)` means the term was not measured for that arm, which is not the same as passing: `Form.` needs an extraction step, `Traceable` needs a tool output for the numbers to trace to, and `Escalated` needs a gate.

`Form.` is per session, over ground-truth sessions, which is what the supplement's Table S3 defines. `Form. days` is the day verdict: a day counts only when every one of its sessions is exact, so it is near zero on days with dozens of cars and is printed next to the per-session rate rather than in place of it.

`Solved` is the conjunction of the state check, traceability, the answer check and the gate. Formulation is not one of its terms, so a wrong formulation is visible in `Form.` alone. It usually still costs the day its `Solved`, through the state check: a schedule optimised on misread parameters breaks the real session's constraint.

`failed` counts rows the arm did not complete. They are written to the rows files with their error and are excluded from every rate above, so a rate must always be read next to it.
