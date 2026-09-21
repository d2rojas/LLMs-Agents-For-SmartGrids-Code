# Informe de experimento: `results_validation_gpt-5.4_stress_rule_based`

Generado el 2026-09-21 15:02 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio results_validation_gpt-5.4_stress_rule_based (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_stress_rule_based
````

- Reports leídos: 1 (`report.rescored.json` usado en 1; el resto `report.json`)
- Modelos: `none:rule_based`
- Métodos: `rule_based`
- Casos: `case14`
- Requests: generadas, N=5 por caso y seed, difficulties=['stress'] (1 report)
- Items por dificultad: stress=10
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0, 1]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-16 13:21
- Costo total: 0.0000 USD (10 items; costo medio 0.00000 USD/item)
- Items totales: 10; ok=6; con error=4; tokens totales=0
- Solved global: 0.0 % (0/10)

Errores por tipo:

| Tipo | Items | Métodos afectados |
|-----------------------|-----|---------------------|
| formulation_failure | 4 | rule_based (4) |


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo. **Esta reconstrucción es ilustrativa, no histórica**: usa el código de `llm/prompts.py` de HOY, así que si el texto del prompt cambió después de que esta corrida se generó, lo que se ve aquí no es lo que el modelo recibió. El registro histórico real es el hash por fila (`system_prompt_hash`, ver sección 1 / `benchmarks/experiment_report.py::section_what_ran`), fijado en el momento de la corrida y nunca recalculado.

### Método `rule_based`

**Sin prompt** — 90 caracteres; rule_based no usa LLM: la request se analiza con un parser de expresiones regulares

````
Load the IEEE 14-bus system and disconnect the transformer branch between bus 7 and bus 8.
````


## 3. Resultados agregados

Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`), en los 4 grupos de `metricas_pfagent_definiciones.md`: **utilidad de tarea** Form. (formulación exacta de las tool calls), V_MAE (p.u., solo sobre peticiones con formulación exacta -- toda fila con herramientas que llega al solver con la formulación correcta da exactamente cero, ver benchmarks/scoring.py) y F_MAE (MW) sobre los items con resultado, Solved (respondió correctamente de extremo a extremo); **corrección solver-grounded** Solver status (convergencia reportada = convergencia real), B_mean (residual medio de KCL de los flujos reportados, MW); **fidelidad** Faith. (por respuesta, no por número: fracción de respuestas donde todo número es trazable a una salida de tool Y viene del solve posterior al último cambio de red) y SFR (fallos declarados con seguridad); **costo** Calls (tool calls medias) y Tok. (tokens medios). Fuera de los 4 grupos, solo en este reporte (no en las tablas del paper): Claim (éxito reclamado sobre un fallo), Escalated y Wrong (silent). Escalated y Wrong (silent) junto con solved_autonomously_rate (no la columna Solved de arriba, que puede solaparse con Escalated -- una abstención de verificación puede caer sobre un item cuyo cálculo de fondo sí era correcto) suman 100 %: dónde termina cada petición -- resuelta sola, entregada a una persona, o mal contestada sin aviso; solo cuenta como Escalated una arquitectura con mecanismo de traspaso real, ver benchmarks.scoring.escalation_check) y $ (costo total USD). Porcentajes en %.

### Por método × caso

| Method | Case | N | Form. | V_MAE solved | V_MAE all | B_mean solved | B_mean all | Solved | Escalated | Wrong-unflagged | Traceable | Tokens | Time (s) | Claim | Escalated | Wrong (silent) | $ |
|----------|------|----|-------------|---------------|---------|----------------|----------|----------|-------------|------------------|---------|------|--------|-------------|-------------|-----------------|------|
| rule_based | case14 | 10 | 50.0 (5/10) | -- | -- | -- | 0 | 0.0 (0/10) | 40.0 (4/10) | 60.0 | 100.0 | 0 | 0.15 | 60.0 (6/10) | 40.0 (4/10) | 60.0 (6/10) | 0.0000 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | stress |
|----------|-------------|
| rule_based | 50.0 (5/10) |

### Solved por dificultad (%, items resueltos / items)

| Method | stress |
|----------|----------|
| rule_based | 0.0 (0/10) |

### Tipos de error de formulación (conteo de items)

| Method | missed_step | ok | unparsed |
|----------|-------------|----|--------|
| rule_based | 1 | 5 | 4 |

### Errores de ejecución por método (conteo de items con `error`)

| Method | formulation_failure |
|----------|-----------------------|
| rule_based | 4 |


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `rule_based`

**Ejemplo: formulación fallida (formulation_exact=False)**

````
request (case14-stress-001-s1, case14, difficulty=stress, seed=1222356006): Load the 14-bus test case (case14), increase the load at bus 3 to 565.2 MW and 114 Mvar (six times its nominal value), increase the active load at bus 4 to 286.8 MW (six times its nominal value), and finally increase the load at bus 9 to 177 MW and 99.6 Mvar (six times its nominal value).
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 3, "p_mw": 565.2, "q_mvar": 114.0}) -> modify_load({"bus_id": 4, "p_mw": 286.8}) -> modify_load({"bus_id": 9, "p_mw": 177.0, "q_mvar": 99.6})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
plan: []
--- Respuesta final ---
I cannot parse this request (unsupported phrasing: 'increase the load at bus 3 to 565.2 MW and 114 Mvar (six times its nominal value)'). No action was taken.
--- Scoring ---
formulation=unparsed (exact=False); V_MAE=--; F_MAE=--; faithful=100.0 %; solved=False (run_failed); flags=-; error=formulation_failure; tokens=0; cost_usd=0.0000; wall=0.0 s
````

**Ejemplo: con bandera de fallo (claimed/stale/abstained)**

````
request (case14-stress-000-s0, case14, difficulty=stress, seed=1813382119): Load the IEEE 14-bus system and disconnect the transformer branch between bus 7 and bus 8.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 7, "to_bus": 8})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 7, "to_bus": 8})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 252.6562386075145, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
tool: disconnect_line({"from_bus": 7, "to_bus": 8})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.898954247812662, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5624 chars más]
  gate: FAIL (reasons=isolated_or_unsolved_buses, mismatch=9.78e-09 MW)
plan: [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "disconnect_line", "args": {"from_bus": 7, "to_bus": 8}}]
--- Respuesta final ---
Loaded case14 (14 buses, 20 branches).
disconnect_line: converged; load 252.656 MW, generation 265.463 MW, losses 12.807 MW; 4 voltage and 0 thermal violation(s).
--- Scoring ---
formulation=ok (exact=True); V_MAE=--; F_MAE=0.00; faithful=100.0 %; solved=False (failure_not_declared); flags=claimed_success_on_failure; error=-; tokens=0; cost_usd=0.0000; wall=0.2 s
````

**Ejemplo: no resuelto**

````
request (case14-stress-000-s1, case14, difficulty=stress, seed=288545019): Load the IEEE 14-bus system and disconnect the transformer branch between bus 7 and bus 8.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 7, "to_bus": 8})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 7, "to_bus": 8})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 256.29258445637254, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
tool: disconnect_line({"from_bus": 7, "to_bus": 8})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.805283121873044, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.0100000 …[5530 chars más]
  gate: FAIL (reasons=isolated_or_unsolved_buses, mismatch=1.2e-08 MW)
plan: [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "disconnect_line", "args": {"from_bus": 7, "to_bus": 8}}]
--- Respuesta final ---
Loaded case14 (14 buses, 20 branches).
disconnect_line: converged; load 256.293 MW, generation 269.238 MW, losses 12.946 MW; 3 voltage and 0 thermal violation(s).
--- Scoring ---
formulation=ok (exact=True); V_MAE=--; F_MAE=0.00; faithful=100.0 %; solved=False (failure_not_declared); flags=claimed_success_on_failure; error=-; tokens=0; cost_usd=0.0000; wall=0.3 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- El gate verificó 11 resultados de flujo, 7 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- 4 items con `formulation_failure`: el método no formuló ninguna tool call.
- Solved de `rule_based`: 0.0 % (0/10).
- Formulación exacta agregada sobre métodos con tools: 50.0 % (5/10).
- Errores de formulación más frecuentes: `unparsed`=4, `missed_step`=1.
- 6 items reclamaron éxito sobre un fallo (claimed_success_on_failure): `rule_based`=6.
- De 10 items en estado de fallo, 4 lo declararon de forma segura (SFR 40.0 % (4/10)).
- 0 de 6 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 100.0 %.
- 10 items esperaban un resultado no convergido (islanded=5, non_converged=5); el método lo declaró correctamente (solved) en 0.0 % (0/10).
- Métodos con tools: 1.70 tool calls medias por item (máximo 4).

## 6. Archivos

Rutas absolutas bajo `results_validation_gpt-5.4_stress_rule_based`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_stress_rule_based/report.json   [leído: report.rescored.json]
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_stress_rule_based/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_stress_rule_based/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_stress_rule_based/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_stress_rule_based/scoreboard_per_case.json
  scoreboard.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_stress_rule_based/scoreboard.rescored.json
  scoreboard_per_case.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_stress_rule_based/scoreboard_per_case.rescored.json
  traces (10 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_stress_rule_based/traces
````

