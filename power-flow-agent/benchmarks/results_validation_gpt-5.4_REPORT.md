# Resumen de bloques: `openrouter:openai/gpt-5.4`

Generado por `benchmarks/build_root_summary.py` a partir de 5 bloques. No vuelve a correr nada ni toca los reportes de cada bloque.

## Bloques

- [results_validation_gpt-5.4_llm_only/REPORT.md](results_validation_gpt-5.4_llm_only/REPORT.md) -- 4 filas de scoreboard_per_case
- [results_validation_gpt-5.4_agents/REPORT.md](results_validation_gpt-5.4_agents/REPORT.md) -- 3 filas de scoreboard_per_case
- [results_validation_gpt-5.4_prompting/REPORT.md](results_validation_gpt-5.4_prompting/REPORT.md) -- 3 filas de scoreboard_per_case
- [results_validation_gpt-5.4_rule_based/REPORT.md](results_validation_gpt-5.4_rule_based/REPORT.md) -- 1 filas de scoreboard_per_case
- [results_validation_gpt-5.4_stress/REPORT.md](results_validation_gpt-5.4_stress/REPORT.md) -- 2 filas de scoreboard_per_case

## Tabla consolidada -- condición `normal`

| Setting | Method | Form. | V_MAE | F_MAE | Solved | Solver status | B_mean | Faith. | SFR | Calls | Tok. | V pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LLM-only | Structured | -- | -- | -- | 0.0 (0/5) | 0.0 (0/5) | -- | 0.0 | -- | n/a | 2390 | 0.0 (0/5) |
| LLM-only | Few-shot | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| LLM-only | Chain-of-thought | -- | -- | -- | 0.0 (0/5) | 0.0 (0/5) | -- | 3.3 | -- | n/a | 2944 | 0.0 (0/5) |
| LLM-only | RAG | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Single-call | Structured | 20.0 (1/5) | $4.33{\times}10^{-3}$ | 1.58 | 20.0 (1/5) | 100.0 (5/5) | $4.68{\times}10^{-3}$ | 100.0 | -- | 1.0 | 4626 | 100.0 (5/5) |
| Single-call | Few-shot | 20.0 (1/5) | $4.33{\times}10^{-3}$ | 1.58 | 20.0 (1/5) | 100.0 (5/5) | $4.68{\times}10^{-3}$ | 100.0 | -- | 1.0 | 4997 | 100.0 (5/5) |
| Single-call | Chain-of-thought | 20.0 (1/5) | $4.33{\times}10^{-3}$ | 1.58 | 20.0 (1/5) | 100.0 (5/5) | $4.68{\times}10^{-3}$ | 100.0 | -- | 1.0 | 5049 | 100.0 (5/5) |
| Single-call | RAG | 20.0 (1/5) | $4.33{\times}10^{-3}$ | 1.58 | 20.0 (1/5) | 100.0 (5/5) | $4.68{\times}10^{-3}$ | 100.0 | -- | 1.0 | 2630 | 100.0 (5/5) |
| Architectures | Rule-based parser, no LLM | 60.0 (3/5) | 0 | 0.00 | 60.0 (3/5) | 100.0 (3/3) | 0 | 100.0 | -- | 1.6 | n/a | 100.0 (5/5) |
| Architectures | Single-call, best prompt | 20.0 (1/5) | $4.33{\times}10^{-3}$ | 1.58 | 20.0 (1/5) | 100.0 (5/5) | $4.68{\times}10^{-3}$ | 100.0 | -- | 1.0 | 4626 | 100.0 (5/5) |
| Architectures | ReAct | 100.0 (5/5) | 0 | 0.00 | 100.0 (5/5) | 100.0 (5/5) | 0 | 100.0 | -- | 2.6 | 9432 | 100.0 (5/5) |
| Architectures | Plan-and-Act | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Architectures | PFAgent: ReAct + gate | 100.0 (5/5) | 0 | 0.00 | 100.0 (5/5) | 100.0 (5/5) | 0 | 100.0 | -- | 2.6 | 9443 | 100.0 (5/5) |


## Tabla consolidada -- condición `stress`

| Setting | Method | Form. | V_MAE | F_MAE | Solved | Solver status | B_mean | Faith. | SFR | Calls | Tok. | V pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LLM-only | Structured | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| LLM-only | Few-shot | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| LLM-only | Chain-of-thought | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| LLM-only | RAG | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Single-call | Structured | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Single-call | Few-shot | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Single-call | Chain-of-thought | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Single-call | RAG | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Architectures | Rule-based parser, no LLM | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Architectures | Single-call, best prompt | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Architectures | ReAct | 50.0 (5/10) | -- | 0.01 | 10.0 (1/10) | 100.0 (10/10) | 0 | 96.6 | 100.0 (5/5) | 3.6 | 16333 | 0.0 (0/10) |
| Architectures | Plan-and-Act | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Architectures | PFAgent: ReAct + gate | 50.0 (5/10) | -- | 0.01 | 10.0 (1/10) | 100.0 (10/10) | 0 | -- | 100.0 (5/5) | 3.9 | 24422 | 0.0 (0/10) |

