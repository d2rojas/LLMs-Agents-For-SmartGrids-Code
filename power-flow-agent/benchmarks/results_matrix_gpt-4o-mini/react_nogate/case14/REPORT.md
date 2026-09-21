# Informe de experimento: `case14`

Generado el 2026-09-21 12:24 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio case14 (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_matrix_gpt-4o-mini/react_nogate/case14
````

- Reports leídos: 1 (`report.rescored.json` usado en 1; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-4o-mini`
- Métodos: `react_nogate`
- Casos: `case14`
- Requests: generadas, N=40 por caso y seed, difficulties=todas (1 report)
- Items por dificultad: plain=10, parameterized=10, multistep=10, ambiguous=10
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-14 01:12
- Costo total: 0.0494 USD (40 items; costo medio 0.00124 USD/item)
- Items totales: 40; ok=40; con error=0; tokens totales=304799
- Solved global: 65.0 % (26/40)

Errores por tipo:

_(ningún item con `error`)_


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo. **Esta reconstrucción es ilustrativa, no histórica**: usa el código de `llm/prompts.py` de HOY, así que si el texto del prompt cambió después de que esta corrida se generó, lo que se ve aquí no es lo que el modelo recibió. El registro histórico real es el hash por fila (`system_prompt_hash`, ver sección 1 / `benchmarks/experiment_report.py::section_what_ran`), fijado en el momento de la corrida y nunca recalculado.

### Método `react_nogate`

**System prompt (SYSTEM_PROMPT_EN)** (reconstrucción con el código actual, no necesariamente histórica) — 1557 caracteres; architecture=react, gate=False, memory=False

````
You are a power system power-flow analysis assistant. You help the user complete power system analysis tasks from natural-language requests.

## What you can do
You complete tasks by calling tool functions:
1. Load an IEEE standard test system (14, 30, 57, 118, 300 buses)
2. Run AC power flow
3. Modify the load at a bus and re-solve
4. Disconnect or reconnect a line and re-solve
5. Query the network status
6. Run an N-1 contingency analysis (disconnect branches one at a time and rank the worst cases)
7. Generate remedial-action suggestions (what-if load shedding or voltage adjustment) to reduce violation risk

## Key rules
- Never fabricate any numerical result. Every voltage, power, loss, or loading value must come from a tool return value.
- If a tool reports an error or a non-converged power flow, say so explicitly and do not report numbers for that state.
- If the request is ambiguous, state the interpretation you are using.
- Bus and line identifiers in the request are MATPOWER 1-based ids; pass them to the tools as given, unless the request itself states a different indexing convention for that identifier (e.g. "(0-based)"), in which case convert it to the MATPOWER 1-based id before calling any tool.
- After a network modification, re-solve before reporting any value.
- Always reply in English.

## Reply format
After each analysis, reply in this structure:
1. One-sentence summary
2. Key numbers (total load, total generation, total losses, voltage range) taken from the tool outputs
3. Violations, if any
4. Suggested next step
````

**User prompt (primer item) = request_text** — 67 caracteres; case=case14, seed=1911784258, k=1, request_id=case14-ambiguous-003-s0

````
Load case14 and disconnect the line between bus ten and bus eleven.
````


## 3. Resultados agregados

Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`), en los 4 grupos de `metricas_pfagent_definiciones.md`: **utilidad de tarea** Form. (formulación exacta de las tool calls), V_MAE (p.u., solo sobre peticiones con formulación exacta -- toda fila con herramientas que llega al solver con la formulación correcta da exactamente cero, ver benchmarks/scoring.py) y F_MAE (MW) sobre los items con resultado, Solved (respondió correctamente de extremo a extremo); **corrección solver-grounded** Solver status (convergencia reportada = convergencia real), B_mean (residual medio de KCL de los flujos reportados, MW); **fidelidad** Faith. (por respuesta, no por número: fracción de respuestas donde todo número es trazable a una salida de tool Y viene del solve posterior al último cambio de red) y SFR (fallos declarados con seguridad); **costo** Calls (tool calls medias) y Tok. (tokens medios). Fuera de los 4 grupos, solo en este reporte (no en las tablas del paper): Claim (éxito reclamado sobre un fallo), Escalated y Wrong (silent). Escalated y Wrong (silent) junto con solved_autonomously_rate (no la columna Solved de arriba, que puede solaparse con Escalated -- una abstención de verificación puede caer sobre un item cuyo cálculo de fondo sí era correcto) suman 100 %: dónde termina cada petición -- resuelta sola, entregada a una persona, o mal contestada sin aviso; solo cuenta como Escalated una arquitectura con mecanismo de traspaso real, ver benchmarks.scoring.escalation_check) y $ (costo total USD). Porcentajes en %.

### Por método × caso

| Method | Case | N | Form. | V_MAE | F_MAE | Solved | Solver status | B_mean | Faith. | SFR | Calls | Tok. | Claim | Escalated | Wrong (silent) | $ |
|---------------|------|----|---------------|-----|-----|---------------|----------------|------|---------------|----|-----|----|-----|----------|-----------------|------|
| react_nogate | case14 | 40 | 97.5 (39/40) | 0 | 0.02 | 65.0 (26/40) | 100.0 (40/40) | 0 | 87.5 (35/40) | -- | 2.3 | 7620 | -- | 0.0 (0/40) | 35.0 (14/40) | 0.0494 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|---------------|----------------|----------------|----------------|-------------|
| react_nogate | 100.0 (10/10) | 100.0 (10/10) | 100.0 (10/10) | 90.0 (9/10) |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|---------------|-------------|----------------|-------------|-------------|
| react_nogate | 80.0 (8/10) | 80.0 (8/10) | 10.0 (1/10) | 90.0 (9/10) |

### Tipos de error de formulación (conteo de items)

| Method | ok | wrong_id |
|---------------|----|--------|
| react_nogate | 39 | 1 |

### Errores de ejecución por método (conteo de items con `error`)

_(ningún item con `error`)_


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `react_nogate`

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
--- Ronda 2 ---
LLM: The case14 has been loaded, and the line between bus 10 and bus 11 has been successfully disconnected.

- **Key numbers**: Total load: 253.85 MW, Total generation: 266.51 MW, Total losses: 12.66 MW, Voltage range: 1.01 to 1.09 p.u.
- **Violations**: There are multiple overvoltage violations at buses …[164 chars más]
--- Respuesta final ---
The case14 has been loaded, and the line between bus 10 and bus 11 has been successfully disconnected.

- **Key numbers**: Total load: 253.85 MW, Total generation: 266.51 MW, Total losses: 12.66 MW, Voltage range: 1.01 to 1.09 p.u.
- **Violations**: There are multiple overvoltage violations at buses 1, 6, 7, 8, 11, and 12.
- **Suggested next step**: Consider running a contingency analysis to assess the impact of the disconnection and identify potential issues.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_and_answer_ok); flags=-; error=-; tokens=4354; cost_usd=0.0007; wall=3.1 s
````

**Ejemplo: formulación fallida (formulation_exact=False)**

````
request (case14-ambiguous-039-s0, case14, difficulty=ambiguous, seed=315597205): Load the 14-bus test case (case14) and set the active load at bus 1 (0-based) to 11 MW.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 2, "p_mw": 11.0})
executed_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 1, "p_mw": 11})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 252.83309137785733, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: modify_load({"bus_id": 1, "p_mw": 11})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.823083955414936, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.0099999 …[6289 chars más]
  gate: PASS (reasons=-, mismatch=6.18e-09 MW)
--- Ronda 3 ---
LLM: The active load at bus 1 has been set to 11 MW, and the power flow has been successfully solved.

- **Total Load:** 263.83 MW
- **Total Generation:** 276.50 MW
- **Total Losses:** 12.67 MW
- **Voltage Range:** 1.035 to 1.090 p.u.

**Violations:** There are multiple overvoltage violations at buses 1, …[166 chars más]
--- Respuesta final ---
The active load at bus 1 has been set to 11 MW, and the power flow has been successfully solved.

- **Total Load:** 263.83 MW
- **Total Generation:** 276.50 MW
- **Total Losses:** 12.67 MW
- **Voltage Range:** 1.035 to 1.090 p.u.

**Violations:** There are multiple overvoltage violations at buses 1, 6, 7, 8, 9, 10, 11, and 12.

**Suggested Next Step:** Consider running a contingency analysis or recommending remedial actions to address the overvoltage violations.
--- Scoring ---
formulation=wrong_id (exact=False); V_MAE=7.59e-06; F_MAE=0.61; faithful=100.0 %; solved=False (formulation); flags=-; error=-; tokens=5362; cost_usd=0.0009; wall=4.0 s
````

**Ejemplo: con bandera de fallo (claimed/stale/abstained)**

````
request (case14-multistep-022-s0, case14, difficulty=multistep, seed=1083806780): Load case14, disconnect the line between bus 9 and bus 10, set the active load at bus 3 to 118.6 MW, set the active load at bus 4 to 53.6 MW, and finally run an N-1 contingency analysis ranked by max violations and report the 8 worst outages.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 9, "to_bus": 10}) -> modify_load({"bus_id": 3, "p_mw": 118.6}) -> modify_load({"bus_id": 4, "p_mw": 53.6}) -> run_n1_contingency({"top_k": 8, "criteria": "max_violations"})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 9, "to_bus": 10}) -> modify_load({"bus_id": 3, "p_mw": 118.6}) -> modify_load({"bus_id": 4, "p_mw": 53.6}) -> run_n1_contingency({"top_k": 8, "criteria": "max_violations"})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 264.0857422973543, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: disconnect_line({"from_bus": 9, "to_bus": 10})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -5.032452347367612, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6092 chars más]
  gate: PASS (reasons=-, mismatch=6.74e-09 MW)
tool: modify_load({"bus_id": 3, "p_mw": 118.6})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0449999999999997, "va_deg": -5.627497640283712, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6074 chars más]
  gate: PASS (reasons=-, mismatch=7.38e-09 MW)
tool: modify_load({"bus_id": 4, "p_mw": 53.6})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -5.672176280633835, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.0100000 …[6073 chars más]
  gate: PASS (reasons=-, mismatch=7.73e-09 MW)
--- Ronda 3 ---
tool: run_n1_contingency({"top_k": 8, "criteria": "max_violations"})
  output: {"plot_type": "n1_ranking", "figure_json": "{\"data\":[{\"cliponaxis\":false,\"hoverinfo\":\"text\",\"hovertext\":[\"\\u003cb\\u003eOutage\\u003c\\u002fb\\u003e: 10-11 (line)\\u003cbr\\u003e\\u003cb\\u003eConverged\\u003c\\u002fb\\u003e: True\\u003cbr\\u003e\\u003cb\\u003eVoltage violations\\u003c\\ …[19612 chars más]
  gate: n/a (no es un resultado de flujo)
--- Ronda 4 ---
LLM: The analysis of the IEEE 14-bus system after the specified modifications has been completed.

1. **Summary**: The N-1 contingency analysis identified the worst outages, with significant voltage violations present.
2. **Key Numbers**: 
   - Total Load: 264.09 MW
   - Total Generation: 278.14 MW
   - …[366 chars más]
--- Respuesta final ---
The analysis of the IEEE 14-bus system after the specified modifications has been completed.

1. **Summary**: The N-1 contingency analysis identified the worst outages, with significant voltage violations present.
2. **Key Numbers**: 
   - Total Load: 264.09 MW
   - Total Generation: 278.14 MW
   - Total Losses: 14.05 MW
   - Voltage Range: 1.0099999999999996 to 1.0900000000000003 pu
3. **Violations**: There are multiple voltage violations at several buses, particularly with bus 1 showing 8 violations.
4. **Suggested Next Step**: Consider implementing remedial actions to address the voltage violations or further analyze the system for potential improvements.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=False (answer_mismatch); flags=stale_state; error=-; tokens=27912; cost_usd=0.0043; wall=6.0 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- Todos los métodos que llegan al solver (react_nogate) tienen V_MAE < 1e-4 p.u. en todos los casos (máximo 1.90e-07 en react_nogate/case14).
- El gate verificó 43 resultados de flujo, 0 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- Ningún item terminó con `error`.
- Solved de `react_nogate`: 65.0 % (26/40).
- Formulación exacta agregada sobre métodos con tools: 97.5 % (39/40).
- Formulación por dificultad: mejor `plain` 100.0 % (10/10), peor `ambiguous` 90.0 % (9/10).
- Errores de formulación más frecuentes: `wrong_id`=1.
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- 1 de 26 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 98.2 %.
- Costo total 0.0494 USD; el método más caro fue `react_nogate` con 0.0494 USD (100 %).
- Métodos con tools: 2.33 tool calls medias por item (máximo 5).

## 6. Archivos

Rutas absolutas bajo `case14`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_matrix_gpt-4o-mini/react_nogate/case14/report.json   [leído: report.rescored.json]
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_matrix_gpt-4o-mini/react_nogate/case14/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_matrix_gpt-4o-mini/react_nogate/case14/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_matrix_gpt-4o-mini/react_nogate/case14/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_matrix_gpt-4o-mini/react_nogate/case14/scoreboard_per_case.json
  scoreboard.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_matrix_gpt-4o-mini/react_nogate/case14/scoreboard.rescored.json
  scoreboard_per_case.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_matrix_gpt-4o-mini/react_nogate/case14/scoreboard_per_case.rescored.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_matrix_gpt-4o-mini/react_nogate/case14/traces
  log: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_matrix_gpt-4o-mini/react_nogate/case14/run.log
````

