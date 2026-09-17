# Informe de experimento: `rule_based`

Generado el 2026-09-16 17:46 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio rule_based (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n40/gpt-5.4/rule_based
````

- Reports leídos: 1 (`report.rescored.json` usado en 1; el resto `report.json`)
- Modelos: `none:rule_based`
- Métodos: `rule_based`
- Casos: `case14`
- Requests: generadas, N=40 por caso y seed, difficulties=todas (1 report)
- Items por dificultad: plain=10, parameterized=10, multistep=10, ambiguous=10
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-16 13:56
- Costo total: 0.0000 USD (40 items; costo medio 0.00000 USD/item)
- Items totales: 40; ok=31; con error=9; tokens totales=0
- Solved global: 72.5 % (29/40)

Errores por tipo:

| Tipo | Items | Métodos afectados |
|-----------------------|-----|---------------------|
| formulation_failure | 9 | rule_based (9) |


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo.

### Método `rule_based`

**Sin prompt** — 67 caracteres; rule_based no usa LLM: la request se analiza con un parser de expresiones regulares

````
Load case14 and disconnect the line between bus ten and bus eleven.
````


## 3. Resultados agregados

Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`), en los 4 grupos de `metricas_pfagent_definiciones.md`: **utilidad de tarea** Form. (formulación exacta de las tool calls), V_MAE (p.u.) y F_MAE (MW) sobre los items con resultado, Solved (respondió correctamente de extremo a extremo); **corrección solver-grounded** Solver status (convergencia reportada = convergencia real), B_mean (residual medio de KCL de los flujos reportados, MW); **fidelidad** Faith. (por respuesta, no por número: fracción de respuestas donde todo número es trazable a una salida de tool Y viene del solve posterior al último cambio de red) y SFR (fallos declarados con seguridad); **costo** Calls (tool calls medias) y Tok. (tokens medios). Fuera de los 4 grupos, solo en este reporte (no en las tablas del paper): Claim (éxito reclamado sobre un fallo), Abst. (abstención en items resolubles) y $ (costo total USD). Porcentajes en %.

### Por método × caso

| Method | Case | N | Form. | V_MAE | F_MAE | Solved | Solver status | B_mean | Faith. | SFR | Calls | Tok. | Claim | Abst. | $ |
|----------|------|----|---------------|--------|-----|---------------|----------------|------|----------------|----|-----|----|-----|-------------|------|
| rule_based | case14 | 40 | 72.5 (29/40) | 1.89e-05 | 0.06 | 72.5 (29/40) | 100.0 (31/31) | 0 | 100.0 (40/40) | -- | 1.9 | n/a | -- | 22.5 (9/40) | 0.0000 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|----------|-------------|----------------|-------------|-------------|
| rule_based | 80.0 (8/10) | 60.0 (6/10) | 80.0 (8/10) | 70.0 (7/10) |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|----------|-------------|----------------|-------------|-------------|
| rule_based | 80.0 (8/10) | 60.0 (6/10) | 80.0 (8/10) | 70.0 (7/10) |

### Tipos de error de formulación (conteo de items)

| Method | ok | unparsed | wrong_id |
|----------|----|--------|--------|
| rule_based | 29 | 9 | 2 |

### Errores de ejecución por método (conteo de items con `error`)

| Method | formulation_failure |
|----------|-----------------------|
| rule_based | 9 |


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `rule_based`

**Ejemplo: resuelto (solved=True)**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 253.84578240591338, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
tool: disconnect_line({"from_bus": 10, "to_bus": 11})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.782856812869876, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5930 chars más]
  gate: PASS (reasons=-, mismatch=7.85e-09 MW)
plan: [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "disconnect_line", "args": {"from_bus": 10, "to_bus": 11}}]
--- Respuesta final ---
Loaded case14 (14 buses, 20 branches).
disconnect_line: converged; load 253.846 MW, generation 266.510 MW, losses 12.665 MW; 6 voltage and 0 thermal violation(s).
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_ok); flags=-; error=-; tokens=0; cost_usd=0.0000; wall=0.2 s
````

**Ejemplo: formulación fallida (formulation_exact=False)**

````
request (case14-ambiguous-011-s0, case14, difficulty=ambiguous, seed=1971893210): Load case14 and set the active load at bus 6 to 14,700 kw.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 6, "p_mw": 14.7})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
plan: []
--- Respuesta final ---
I cannot parse this request (unsupported phrasing: 'set the active load at bus 6 to 14,700 kw'). No action was taken.
--- Scoring ---
formulation=unparsed (exact=False); V_MAE=--; F_MAE=--; faithful=-- %; solved=False (run_failed); flags=abstained,abstained_on_solvable; error=formulation_failure; tokens=0; cost_usd=0.0000; wall=0.0 s
````

**Ejemplo: con bandera de fallo (claimed/stale/abstained)**

````
request (case14-multistep-022-s0, case14, difficulty=multistep, seed=1083806780): Load case14, disconnect the line between bus 9 and bus 10, set the active load at bus 3 to 118.6 MW, set the active load at bus 4 to 53.6 MW, and finally run an N-1 contingency analysis ranked by max violations and report the 8 worst outages.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 9, "to_bus": 10}) -> modify_load({"bus_id": 3, "p_mw": 118.6}) -> modify_load({"bus_id": 4, "p_mw": 53.6}) -> run_n1_contingency({"top_k": 8, "criteria": "max_violations"})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
plan: []
--- Respuesta final ---
I cannot parse this request (unsupported phrasing: 'report the 8 worst outages'). No action was taken.
--- Scoring ---
formulation=unparsed (exact=False); V_MAE=--; F_MAE=--; faithful=-- %; solved=False (run_failed); flags=abstained,abstained_on_solvable; error=formulation_failure; tokens=0; cost_usd=0.0000; wall=0.0 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- Todos los métodos que llegan al solver (rule_based) tienen V_MAE < 1e-4 p.u. en todos los casos (máximo 1.89e-05 en rule_based/case14).
- El gate verificó 44 resultados de flujo, 0 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- 9 items con `formulation_failure`: el método no formuló ninguna tool call.
- Solved de `rule_based`: 72.5 % (29/40).
- Formulación exacta agregada sobre métodos con tools: 72.5 % (29/40).
- Formulación por dificultad: mejor `plain` 80.0 % (8/10), peor `parameterized` 60.0 % (6/10).
- Errores de formulación más frecuentes: `unparsed`=9, `wrong_id`=2.
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- 0 de 23 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 100.0 %.
- Métodos con tools: 1.88 tool calls medias por item (máximo 5).

## 6. Archivos

Rutas absolutas bajo `rule_based`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n40/gpt-5.4/rule_based/report.json   [leído: report.rescored.json]
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n40/gpt-5.4/rule_based/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n40/gpt-5.4/rule_based/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n40/gpt-5.4/rule_based/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n40/gpt-5.4/rule_based/scoreboard_per_case.json
  scoreboard.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n40/gpt-5.4/rule_based/scoreboard.rescored.json
  scoreboard_per_case.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n40/gpt-5.4/rule_based/scoreboard_per_case.rescored.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n40/gpt-5.4/rule_based/traces
````

