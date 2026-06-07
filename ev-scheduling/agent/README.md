# Agentic pipeline

1. **Plan**: Parse user request → objective, horizon, constraints, session params.
2. **Optimize**: Formulate and solve (CVXPY) cost-minimization with slack; compute peak load.
3. **Validate**: Constraint checker → feasibility, unmet energy, peak load.
4. **Refine**: On parsing/implementation errors, fix structured representation and re-solve.
5. **Explain**: Extract schedule-derived facts; generate NL explanation grounded in computed artifacts.

Stretch: interactive what-if (charger outage, demand surge) by modifying constraints and re-solving.
