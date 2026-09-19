# Informe de experimento: `plan_act_nogate`

Generado el 2026-09-18 22:47 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio plan_act_nogate (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_plan_structured/gpt-5.4/plan_act_nogate
````

- Reports leídos: 1 (`report.rescored.json` usado en 1; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-5.4`
- Métodos: `plan_act_nogate`
- Casos: `case14`
- Requests: generadas, N=40 por caso y seed, difficulties=todas (1 report)
- Items por dificultad: plain=10, parameterized=10, multistep=10, ambiguous=10
- System prompt: hash `7da5e2a37ec4` (40 filas)
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-18 22:31
- Costo total: 0.4028 USD (40 items; costo medio 0.01007 USD/item)
- Items totales: 40; ok=40; con error=0; tokens totales=107812
- Solved global: 32.5 % (13/40)

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
|------------------|------|----|---------------|-----|-----|---------------|----------------|--------|----------------|----|-----|----|-----|----------|-----------------|------|
| plan_act_nogate | case14 | 40 | 32.5 (13/40) | 0 | 1.97 | 32.5 (13/40) | 100.0 (40/40) | 3.57e-02 | 100.0 (40/40) | -- | 1.6 | 2695 | -- | 0.0 (0/40) | 67.5 (27/40) | 0.4028 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|------------------|-------------|----------------|----------|-------------|
| plan_act_nogate | 60.0 (6/10) | 50.0 (5/10) | 0.0 (0/10) | 20.0 (2/10) |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|------------------|-------------|----------------|----------|-------------|
| plan_act_nogate | 60.0 (6/10) | 50.0 (5/10) | 0.0 (0/10) | 20.0 (2/10) |

### Tipos de error de formulación (conteo de items)

| Method | extra_arg_changes_result | missed_step | ok |
|------------------|------------------------------|-------------|----|
| plan_act_nogate | 3 | 24 | 13 |

### Errores de ejecución por método (conteo de items con `error`)

_(ningún item con `error`)_


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `plan_act_nogate`

**Ejemplo: resuelto (solved=True)**

````
request (case14-ambiguous-007-s0, case14, difficulty=ambiguous, seed=2073320062): Load the 14-bus test case (case14) and disconnect the line between bus 6 and bus 13 (1-based).
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 6, "to_bus": 13})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 6, "to_bus": 13})
fuente de la traza: archivo de traza completo
--- Ronda 1 [plan] ---
tool_call: load_case({"case_name":"case14"})
tool_call: disconnect_line({"from_bus":6,"to_bus":13})
--- Ronda 2 [act] ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 261.9028323717408, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
tool: disconnect_line({"from_bus": 6, "to_bus": 13})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -5.104476346710827, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5772 chars más]
  gate: PASS (reasons=-, mismatch=5.12e-08 MW)
--- Ronda 3 [answer] [final] ---
LLM: 1. **One-sentence summary**  
The IEEE 14-bus test case was loaded and the line between bus 6 and bus 13 was disconnected; the post-contingency AC power flow converged.

2. **Key numbers**  
- Total load: **261.9028323717408 MW**  
- Total generation: **276.66348753955316 MW**  
- Total losses: **14 …[676 chars más]
--- Respuesta final ---
1. **One-sentence summary**  
The IEEE 14-bus test case was loaded and the line between bus 6 and bus 13 was disconnected; the post-contingency AC power flow converged.

2. **Key numbers**  
- Total load: **261.9028323717408 MW**  
- Total generation: **276.66348753955316 MW**  
- Total losses: **14.760655219011168 MW**  
- Voltage range: **0.9989276391872052 pu** (bus 13) to **1.09 pu** (bus 8)

3. **Violations, if any**  
- **Voltage violations:**  
  - Bus 1: **1.06 pu** overvoltage  
  - Bus 6: **1.07 pu** overvoltage  
  - Bus 7: **1.0571672643378551 pu** overvoltage  
  - Bus 8: **1.09 pu** overvoltage  
  - Bus 11: **1.0530887682307093 pu** overvoltage  
- **Thermal violations:** none reported  
- Disconnected line status: line **6–13** has **0.0 MW**, **0.0 MVAr**, **0.0%** loading …[176 chars más]
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_ok); flags=-; error=-; tokens=3952; cost_usd=0.0147; wall=6.0 s
````

**Ejemplo: formulación fallida (formulation_exact=False)**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: load_case({"case_name": "case14"})
fuente de la traza: archivo de traza completo
--- Ronda 1 [plan] ---
tool_call: load_case({"case_name":"case14"})
--- Ronda 2 [act] ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 253.84578240591338, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 3 [answer] [final] ---
LLM: 1. One-sentence summary  
I loaded IEEE case14, but the requested line disconnection between bus 10 and bus 11 was not performed in the available tool outputs.

2. Key numbers  
- Total load: 253.84578240591338 MW  
- Total generation capacity: 772.4000000000001 MW  
- Total generation: not availabl …[427 chars más]
--- Respuesta final ---
1. One-sentence summary  
I loaded IEEE case14, but the requested line disconnection between bus 10 and bus 11 was not performed in the available tool outputs.

2. Key numbers  
- Total load: 253.84578240591338 MW  
- Total generation capacity: 772.4000000000001 MW  
- Total generation: not available from the tool outputs  
- Total losses: not available from the tool outputs  
- Voltage range: not available from the tool outputs

3. Violations, if any  
No power-flow or post-contingency results were provided, so violations cannot be determined.

4. Suggested next step  
Disconnect the line between buses 10 and 11 and run a power flow so the updated operating point, losses, voltages, and any violations can be reported.
--- Scoring ---
formulation=missed_step (exact=False); V_MAE=2.05e-03; F_MAE=1.39; faithful=100.0 %; solved=False (formulation); flags=-; error=-; tokens=1220; cost_usd=0.0054; wall=4.3 s
````

**Ejemplo: no resuelto**

````
request (case14-ambiguous-011-s0, case14, difficulty=ambiguous, seed=1971893210): Load case14 and set the active load at bus 6 to 14,700 kw.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 6, "p_mw": 14.7})
executed_calls: load_case({"case_name": "case14"})
fuente de la traza: archivo de traza completo
--- Ronda 1 [plan] ---
tool_call: load_case({"case_name":"case14"})
--- Ronda 2 [act] ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 263.13580543670497, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 3 [answer] [final] ---
LLM: 1. One-sentence summary  
I loaded IEEE case14, but the active load at bus 6 has not been changed yet because no load-modification tool output is available.

2. Key numbers  
- Total load: 263.13580543670497 MW  
- Total generation capacity: 772.4000000000001 MW  
- Buses: 14  
- Generators: 5  
- L …[294 chars más]
--- Respuesta final ---
1. One-sentence summary  
I loaded IEEE case14, but the active load at bus 6 has not been changed yet because no load-modification tool output is available.

2. Key numbers  
- Total load: 263.13580543670497 MW  
- Total generation capacity: 772.4000000000001 MW  
- Buses: 14  
- Generators: 5  
- Lines: 20  
- Loads: 11  

3. Violations, if any  
No power-flow or violation results are available from the tool outputs provided.

4. Suggested next step  
Run the load-modification step to set bus 6 active load to 14,700 kW, then re-solve the power flow and report the updated system results.
--- Scoring ---
formulation=missed_step (exact=False); V_MAE=1.54e-04; F_MAE=0.82; faithful=100.0 %; solved=False (formulation); flags=-; error=-; tokens=1221; cost_usd=0.0053; wall=4.1 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- V_MAE >= 1e-4 p.u. en 1 filas método×caso con solver: plan_act_nogate/case14 (1.40e-03).
- El gate verificó 15 resultados de flujo, 0 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- Ningún item terminó con `error`.
- Solved de `plan_act_nogate`: 32.5 % (13/40).
- Formulación exacta agregada sobre métodos con tools: 32.5 % (13/40).
- Formulación por dificultad: mejor `plain` 60.0 % (6/10), peor `multistep` 0.0 % (0/10).
- Errores de formulación más frecuentes: `missed_step`=24, `extra_arg_changes_result`=3.
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- 0 de 7 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 100.0 %.
- Costo total 0.4028 USD; el método más caro fue `plan_act_nogate` con 0.4028 USD (100 %).
- Métodos con tools: 1.55 tool calls medias por item (máximo 5).

## 6. Archivos

Rutas absolutas bajo `plan_act_nogate`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_plan_structured/gpt-5.4/plan_act_nogate/report.json   [leído: report.rescored.json]
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_plan_structured/gpt-5.4/plan_act_nogate/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_plan_structured/gpt-5.4/plan_act_nogate/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_plan_structured/gpt-5.4/plan_act_nogate/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_plan_structured/gpt-5.4/plan_act_nogate/scoreboard_per_case.json
  scoreboard.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_plan_structured/gpt-5.4/plan_act_nogate/scoreboard.rescored.json
  scoreboard_per_case.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_plan_structured/gpt-5.4/plan_act_nogate/scoreboard_per_case.rescored.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_plan_structured/gpt-5.4/plan_act_nogate/traces
````

