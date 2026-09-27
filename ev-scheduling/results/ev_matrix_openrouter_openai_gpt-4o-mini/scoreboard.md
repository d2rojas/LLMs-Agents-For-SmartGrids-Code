# EV Scheduling Benchmark Matrix

model=openrouter:openai/gpt-4o-mini resolved=openai/gpt-4o-mini  
days=20 seeds=[0] repeats=1 items/arm=20  
data_source=cache synthetic=False requests_digest=sha256:77e41af52a48db623768923f0b30c79966638643baf21b68db26b990da867967  
budget_ceiling_usd=3.0 spent_usd=0.4696 traceability_policy=grounded_only  

| arm | items | failed | Solved | Escalated | Wrong unflagged | Form. | FR | Traceable | Answer | gap % | cost $ | repaired | USD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| optimum | 20 | 0 | 100.0% (20/20) | 0.0% (0/20) | 0.0% (0/20) | n/a (0/0) | 100.0% (20/20) | n/a (0/0) | 100.0% (19/19) | 0.00 | 100.83 | n/a (0/0) | 0.0000 |
| charge_asap | 20 | 0 | 0.0% (0/20) | 0.0% (0/20) | 100.0% (20/20) | n/a (0/0) | 15.0% (3/20) | n/a (0/0) | 73.7% (14/19) | 37.82 | 135.11 | n/a (0/0) | 0.0000 |
| llm_only:structured | 20 | 0 | 0.0% (0/20) | 0.0% (0/20) | 100.0% (20/20) | n/a (0/0) | 100.0% (20/20) | n/a (0/0) | 0.0% (0/19) | -100.00 | 0.00 | 100.0% (20/20) | 0.2035 |
| llm_only:chain_of_thought | 20 | 0 | 0.0% (0/20) | 0.0% (0/20) | 100.0% (20/20) | n/a (0/0) | 100.0% (20/20) | n/a (0/0) | 0.0% (0/19) | -100.00 | 0.00 | 100.0% (20/20) | 0.2042 |
| evagent | 20 | 0 | 0.0% (0/20) | 0.0% (0/20) | 100.0% (20/20) | 0.0% (0/20) | 0.0% (0/20) | 100.0% (20/20) | 36.8% (7/19) | 0.17 | 100.90 | n/a (0/0) | 0.0620 |

Every rate carries its denominator. `n/a (0/0)` means the term was not measured for that arm, which is not the same as passing: `Form.` needs an extraction step, `Traceable` needs a tool output for the numbers to trace to, and `Escalated` needs a gate.

`failed` counts rows the arm did not complete. They are written to the rows files with their error and are excluded from every rate above, so a rate must always be read next to it.
