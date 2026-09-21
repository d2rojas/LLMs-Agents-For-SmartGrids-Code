# Informe de experimento: `case14`

Generado el 2026-09-21 08:33 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio case14 (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/plan_act_nogate/case14
````

- Reports leídos: 1 (`report.rescored.json` usado en 0; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-5.6-sol`
- Métodos: `plan_act_nogate`
- Casos: `case14`
- Requests: generadas, N=40 por caso y seed, difficulties=todas (1 report)
- Items por dificultad: plain=10, parameterized=10, multistep=10, ambiguous=10
- System prompt: hash `7da5e2a37ec4` (40 filas)
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-21 08:12
- Costo total: 0.6483 USD (40 items; costo medio 0.01621 USD/item)
- Items totales: 40; ok=40; con error=0; tokens totales=256687
- Solved global: 77.5 % (31/40)

Errores por tipo:

_(ningún item con `error`)_


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo. **Esta reconstrucción es ilustrativa, no histórica**: usa el código de `llm/prompts.py` de HOY, así que si el texto del prompt cambió después de que esta corrida se generó, lo que se ve aquí no es lo que el modelo recibió. El registro histórico real es el hash por fila (`system_prompt_hash`, ver sección 1 / `benchmarks/experiment_report.py::section_what_ran`), fijado en el momento de la corrida y nunca recalculado.

### Método `plan_act_nogate` (system_prompt_hash real de esta fila: `7da5e2a37ec4`)

**System prompt (SYSTEM_PROMPT_EN)** (reconstrucción con el código actual, no necesariamente histórica) — 1557 caracteres; architecture=plan_act, gate=False, memory=False

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

**PLAN_SYSTEM_PROMPT (cabecera)** — 1043 caracteres; primeras 12 líneas de 1424 caracteres; catálogo de tools omitido

````
You are the planner of a power-system analysis agent. You cannot call tools yourself. Given the user's request, output ONLY a JSON object of the form
{"plan": [{"tool": "<tool_name>", "args": {...}}, ...]}
listing, in execution order, every tool call needed to answer the request. Use only the tools below with exactly these argument names (* = required). Do not include explanations, markdown, or any text outside the JSON.

Available tools:
- load_case(case_name: string*): Load IEEE test case.
- run_powerflow((none)): Run power flow on current case.
- modify_load(bus_id: integer*, p_mw: number*, q_mvar: number): Modify bus load and recompute.
- disconnect_line(from_bus: integer*, to_bus: integer*): Disconnect line/branch between two buses and recompute.
- reconnect_line(from_bus: integer*, to_bus: integer*): Reconnect line/branch between two buses and recompute.
- get_most_loaded_branch((none)): Get most loaded branch.
- run_n1_contingency(top_k: integer, criteria: string, max_candidates: integer): Run N-1 contingency analysis.
…
````

**FINAL_ANSWER_INSTRUCTION (ronda final)** — 158 caracteres; se añade tras ejecutar el plan

````
Write the final answer for the user strictly from the tool outputs above. Never invent numbers; if a tool reported an error or a non-converged result, say so.
````


## 3. Resultados agregados

Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`), en los 4 grupos de `metricas_pfagent_definiciones.md`: **utilidad de tarea** Form. (formulación exacta de las tool calls), V_MAE (p.u., solo sobre peticiones con formulación exacta -- toda fila con herramientas que llega al solver con la formulación correcta da exactamente cero, ver benchmarks/scoring.py) y F_MAE (MW) sobre los items con resultado, Solved (respondió correctamente de extremo a extremo); **corrección solver-grounded** Solver status (convergencia reportada = convergencia real), B_mean (residual medio de KCL de los flujos reportados, MW); **fidelidad** Faith. (por respuesta, no por número: fracción de respuestas donde todo número es trazable a una salida de tool Y viene del solve posterior al último cambio de red) y SFR (fallos declarados con seguridad); **costo** Calls (tool calls medias) y Tok. (tokens medios). Fuera de los 4 grupos, solo en este reporte (no en las tablas del paper): Claim (éxito reclamado sobre un fallo), Escalated y Wrong (silent). Escalated y Wrong (silent) junto con solved_autonomously_rate (no la columna Solved de arriba, que puede solaparse con Escalated -- una abstención de verificación puede caer sobre un item cuyo cálculo de fondo sí era correcto) suman 100 %: dónde termina cada petición -- resuelta sola, entregada a una persona, o mal contestada sin aviso; solo cuenta como Escalated una arquitectura con mecanismo de traspaso real, ver benchmarks.scoring.escalation_check) y $ (costo total USD). Porcentajes en %.

### Por método × caso

| Method | Case | N | Form. | V_MAE | F_MAE | Solved | Solver status | B_mean | Faith. | SFR | Calls | Tok. | Claim | Escalated | Wrong (silent) | $ |
|------------------|------|----|---------------|-----|-----|---------------|----------------|--------|---------------|----|-----|----|-----|----------|-----------------|------|
| plan_act_nogate | case14 | 40 | 77.5 (31/40) | 0 | 0.05 | 77.5 (31/40) | 100.0 (40/40) | 1.82e-04 | 97.5 (39/40) | -- | 2.9 | 6417 | -- | 0.0 (0/40) | 22.5 (9/40) | 0.6483 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|------------------|-------------|----------------|-------------|-------------|
| plan_act_nogate | 80.0 (8/10) | 80.0 (8/10) | 80.0 (8/10) | 70.0 (7/10) |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|------------------|-------------|----------------|-------------|-------------|
| plan_act_nogate | 80.0 (8/10) | 80.0 (8/10) | 80.0 (8/10) | 70.0 (7/10) |

### Tipos de error de formulación (conteo de items)

| Method | extra_arg_changes_result | invalid_value | ok | wrong_id |
|------------------|------------------------------|----------------|----|--------|
| plan_act_nogate | 2 | 5 | 31 | 2 |

### Errores de ejecución por método (conteo de items con `error`)

_(ningún item con `error`)_


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `plan_act_nogate`

**Ejemplo: resuelto (solved=True)**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
fuente de la traza: archivo de traza completo
--- Ronda 1 [plan] ---
LLM: {"plan":[{"tool":"load_case","args":{"case_name":"case14"}},{"tool":"disconnect_line","args":{"from_bus":10,"to_bus":11}}]}
--- Ronda 2 [act] ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 253.84578240591338, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
tool: disconnect_line({"from_bus": 10, "to_bus": 11})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.782856812869876, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5930 chars más]
  gate: PASS (reasons=-, mismatch=7.85e-09 MW)
--- Ronda 3 [answer] [final] ---
LLM: The IEEE 14-bus case was loaded, the line between buses 10 and 11 was disconnected, and the AC power flow converged successfully.

**Key numbers**
- Total load: **253.846 MW**
- Total generation: **266.510 MW**
- Total active-power losses: **12.665 MW**
- Voltage range: **1.010 p.u.** at bus 3 to ** …[348 chars más]
--- Respuesta final ---
The IEEE 14-bus case was loaded, the line between buses 10 and 11 was disconnected, and the AC power flow converged successfully.

**Key numbers**
- Total load: **253.846 MW**
- Total generation: **266.510 MW**
- Total active-power losses: **12.665 MW**
- Voltage range: **1.010 p.u.** at bus 3 to **1.090 p.u.** at bus 8
- Disconnected line 10–11 flow: **0 MW / 0 MVAr**

**Violations**
- Overvoltage at buses **1 (1.060 p.u.), 6 (1.070 p.u.), 7 (1.057 p.u.), 8 (1.090 p.u.), 11 (1.064 p.u.), and 12 (1.054 p.u.)**
- No thermal violations

**Suggested next step**
Evaluate remedial voltage-control actions to reduce the six overvoltage violations.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_ok); flags=-; error=-; tokens=3799; cost_usd=0.0101; wall=9.7 s
````

**Ejemplo: formulación fallida (formulation_exact=False)**

````
request (case14-ambiguous-027-s0, case14, difficulty=ambiguous, seed=203647507): Load the IEEE 14-bus system and set the active load at bus 10 (0-based) to 4.7 MW.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 11, "p_mw": 4.7})
executed_calls: load_case({"case_name": "IEEE 14-bus"}) -> modify_load({"bus_id": 10, "p_mw": 4.7})
fuente de la traza: archivo de traza completo
--- Ronda 1 [plan] ---
LLM: {"plan":[{"tool":"load_case","args":{"case_name":"IEEE 14-bus"}},{"tool":"modify_load","args":{"bus_id":10,"p_mw":4.7}}]}
--- Ronda 2 [act] ---
tool: load_case({"case_name": "IEEE 14-bus"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 263.708166484847, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
tool: modify_load({"bus_id": 10, "p_mw": 4.7})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -4.9130978627475494, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_ …[6449 chars más]
  gate: PASS (reasons=-, mismatch=4.77e-09 MW)
--- Ronda 3 [answer] [final] ---
LLM: The IEEE 14-bus system loaded and the power flow converged, but the 4.7 MW load was applied to MATPOWER bus 10 rather than bus 11, which corresponds to the requested 0-based bus 10.

**Key numbers**
- Total load: **260.0198 MW**
- Total generation: **273.5555 MW**
- Total active-power losses: **13.5 …[249 chars más]
--- Respuesta final ---
The IEEE 14-bus system loaded and the power flow converged, but the 4.7 MW load was applied to MATPOWER bus 10 rather than bus 11, which corresponds to the requested 0-based bus 10.

**Key numbers**
- Total load: **260.0198 MW**
- Total generation: **273.5555 MW**
- Total active-power losses: **13.5358 MW**
- Voltage range: **1.0100–1.0900 p.u.**

**Violations**
- Overvoltages at buses **1, 6, 7, 8, 9, 10, 11, 12, and 13**
- No thermal violations

**Suggested next step**
- Reapply the **4.7 MW** active load to MATPOWER bus **11** and re-solve.
--- Scoring ---
formulation=wrong_id (exact=False); V_MAE=5.79e-04; F_MAE=1.22; faithful=100.0 %; solved=False (formulation); flags=-; error=-; tokens=4220; cost_usd=0.0124; wall=12.6 s
````

**Ejemplo: no resuelto**

````
request (case14-ambiguous-035-s0, case14, difficulty=ambiguous, seed=1514345873): Load the 14-bus test case (case14) and set the active load at bus 5 to 3.8 MVA.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 5, "p_mw": 3.8})
executed_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 5, "p_mw": 3.8, "q_mvar": 1.6})
fuente de la traza: archivo de traza completo
--- Ronda 1 [plan] ---
LLM: {"plan":[{"tool":"load_case","args":{"case_name":"case14"}},{"tool":"modify_load","args":{"bus_id":5,"p_mw":3.8,"q_mvar":1.6}}]}
--- Ronda 2 [act] ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 257.05241168650946, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
tool: modify_load({"bus_id": 5, "p_mw": 3.8, "q_mvar": 1.6})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -4.891489369958464, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6403 chars más]
  gate: PASS (reasons=-, mismatch=5.9e-09 MW)
--- Ronda 3 [answer] [final] ---
LLM: The IEEE 14-bus case was loaded, and bus 5 active load was set to **3.8 MW**—interpreting “active load” as MW while retaining **1.6 MVAr** reactive load; the AC power flow converged.

**Key numbers**
- Total load: **252.6396 MW**
- Total generation: **265.5608 MW**
- Total losses: **12.9211 MW**
- V …[279 chars más]
--- Respuesta final ---
The IEEE 14-bus case was loaded, and bus 5 active load was set to **3.8 MW**—interpreting “active load” as MW while retaining **1.6 MVAr** reactive load; the AC power flow converged.

**Key numbers**
- Total load: **252.6396 MW**
- Total generation: **265.5608 MW**
- Total losses: **12.9211 MW**
- Voltage range: **1.0100–1.0900 p.u.**
- Bus 5 voltage: **1.0195 p.u.**

**Violations**
- Overvoltage at buses **1, 6, 7, 8, 9, 10, 11, 12, and 13**
- No thermal violations

**Suggested next step**
- Review or adjust generator voltage setpoints to reduce the reported overvoltages.
--- Scoring ---
formulation=extra_arg_changes_result (exact=False); V_MAE=1.04e-05; F_MAE=0.00; faithful=85.7 %; solved=False (formulation); flags=-; error=-; tokens=4388; cost_usd=0.0140; wall=18.7 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- Todos los métodos que llegan al solver (plan_act_nogate) tienen V_MAE < 1e-4 p.u. en todos los casos (máximo 2.12e-05 en plan_act_nogate/case14).
- El gate verificó 57 resultados de flujo, 0 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- Ningún item terminó con `error`.
- Solved de `plan_act_nogate`: 77.5 % (31/40).
- Formulación exacta agregada sobre métodos con tools: 77.5 % (31/40).
- Formulación por dificultad: mejor `plain` 80.0 % (8/10), peor `ambiguous` 70.0 % (7/10).
- Errores de formulación más frecuentes: `invalid_value`=5, `extra_arg_changes_result`=2, `wrong_id`=2.
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- 0 de 26 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 99.6 %.
- Costo total 0.6483 USD; el método más caro fue `plan_act_nogate` con 0.6483 USD (100 %).
- Métodos con tools: 2.90 tool calls medias por item (máximo 6).

## 6. Archivos

Rutas absolutas bajo `case14`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/plan_act_nogate/case14/report.json
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/plan_act_nogate/case14/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/plan_act_nogate/case14/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/plan_act_nogate/case14/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/plan_act_nogate/case14/scoreboard_per_case.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/plan_act_nogate/case14/traces
  log: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/plan_act_nogate/case14/run.attempt1.log
````

