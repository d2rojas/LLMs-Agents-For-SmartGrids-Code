# Informe de experimento: `results_smoke_v6v7_live`

Generado el 2026-09-21 13:38 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio results_smoke_v6v7_live (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_smoke_v6v7_live
````

- Reports leídos: 1 (`report.rescored.json` usado en 0; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-4o-mini`
- Métodos: `pfagent`
- Casos: `case14`
- Requests: generadas, N=1 por caso y seed, difficulties=['plain'] (1 report)
- Items por dificultad: plain=5
- System prompt: hash `7da5e2a37ec4` (5 filas)
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0, 1, 2, 3, 4]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-21 13:38
- Costo total: 0.0000 USD (5 items; costo medio 0.00000 USD/item)
- Items totales: 5; ok=5; con error=0; tokens totales=44777
- Solved global: 60.0 % (3/5)

Errores por tipo:

_(ningún item con `error`)_


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo. **Esta reconstrucción es ilustrativa, no histórica**: usa el código de `llm/prompts.py` de HOY, así que si el texto del prompt cambió después de que esta corrida se generó, lo que se ve aquí no es lo que el modelo recibió. El registro histórico real es el hash por fila (`system_prompt_hash`, ver sección 1 / `benchmarks/experiment_report.py::section_what_ran`), fijado en el momento de la corrida y nunca recalculado.

### Método `pfagent` (system_prompt_hash real de esta fila: `7da5e2a37ec4`)

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

**User prompt (primer item) = request_text** — 90 caracteres; case=case14, seed=1813382119, k=1, request_id=case14-plain-000-s0

````
Load case14 and run the power flow, then report the bus with the lowest voltage magnitude.
````


## 3. Resultados agregados

Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`), en los 4 grupos de `metricas_pfagent_definiciones.md`: **utilidad de tarea** Form. (formulación exacta de las tool calls), V_MAE (p.u., solo sobre peticiones con formulación exacta -- toda fila con herramientas que llega al solver con la formulación correcta da exactamente cero, ver benchmarks/scoring.py) y F_MAE (MW) sobre los items con resultado, Solved (respondió correctamente de extremo a extremo); **corrección solver-grounded** Solver status (convergencia reportada = convergencia real), B_mean (residual medio de KCL de los flujos reportados, MW); **fidelidad** Faith. (por respuesta, no por número: fracción de respuestas donde todo número es trazable a una salida de tool Y viene del solve posterior al último cambio de red) y SFR (fallos declarados con seguridad); **costo** Calls (tool calls medias) y Tok. (tokens medios). Fuera de los 4 grupos, solo en este reporte (no en las tablas del paper): Claim (éxito reclamado sobre un fallo), Escalated y Wrong (silent). Escalated y Wrong (silent) junto con solved_autonomously_rate (no la columna Solved de arriba, que puede solaparse con Escalated -- una abstención de verificación puede caer sobre un item cuyo cálculo de fondo sí era correcto) suman 100 %: dónde termina cada petición -- resuelta sola, entregada a una persona, o mal contestada sin aviso; solo cuenta como Escalated una arquitectura con mecanismo de traspaso real, ver benchmarks.scoring.escalation_check) y $ (costo total USD). Porcentajes en %.

### Por método × caso

| Method | Case | N | Form. | V_MAE solved | V_MAE all | B_mean solved | B_mean all | Solved | Escalated | Wrong-unflagged | Traceable | Tokens | Time (s) | Claim | Escalated | Wrong (silent) | $ |
|-------|------|----|-------------|---------------|---------|----------------|----------|----------|----------|------------------|---------|------|--------|-----|----------|-----------------|----|
| pfagent | case14 | 5 | 100.0 (5/5) | 0 | 0 | 0 | 0 | 60.0 (3/5) | 40.0 (2/5) | 0.0 | 100.0 | 8955 | 5.44 | -- | 40.0 (2/5) | 0.0 (0/5) | -- |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain |
|-------|-------------|
| pfagent | 100.0 (5/5) |

### Solved por dificultad (%, items resueltos / items)

| Method | plain |
|-------|----------|
| pfagent | 60.0 (3/5) |

### Verificación final (pfagent: V(x,c,z,y) aplicado a la respuesta final)

`pass_first` = pasó al primer intento; `pass_retry` = pasó tras el único reintento con el veredicto añadido; `abstained` = falló dos veces, respuesta forzada a fallo declarado sin números; `retry_mutation` = el reintento intentó una herramienta que muta la red (bloqueada, nunca ejecutada; cuenta como abstención) — ver "Integridad del reintento" abajo. N = items con `final_gate` activo (no todos los métodos lo tienen).

| Method | N | pass_first | pass_retry | abstained | retry_mutation |
|-------|----|----------|----------|----------|-----------------|
| pfagent | 5 | 60.0 (3/5) | 0.0 (0/5) | 40.0 (2/5) | 0.0 (0/5) |


### Integridad del reintento

De 2 ítem(s) que llegaron a un reintento, 0 intentaron una herramienta que muta la red (bloqueada) en vez de corregir el reporte; se cuentan como abstención, no como "pasó". El mensaje de reintento ya no sugiere la corrección específica (p. ej. "reconnect...") y bloquea estructuralmente `modify_load`, `disconnect_line`, `reconnect_line`, `apply_remedial_action` y `load_case` mientras el reintento está en efecto.

### Tipos de error de formulación (conteo de items)

| Method | ok |
|-------|----|
| pfagent | 5 |

### Errores de ejecución por método (conteo de items con `error`)

_(ningún item con `error`)_


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `pfagent`

**Ejemplo: resuelto (solved=True)**

````
request (case14-plain-000-s2, case14, difficulty=plain, seed=2053067962): Load the 14-bus test case (case14) and run an N-1 contingency analysis and report the worst single outage.
intended_calls: load_case({"case_name": "case14"}) -> run_n1_contingency({})
executed_calls: load_case({"case_name": "case14"}) -> run_n1_contingency({"top_k": 1})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 262.2745631531137, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: run_n1_contingency({"top_k": 1})
  output: {"plot_type": "n1_ranking", "figure_json": "{\"data\":[{\"cliponaxis\":false,\"hoverinfo\":\"text\",\"hovertext\":[\"\\u003cb\\u003eOutage\\u003c\\u002fb\\u003e: 1-5 (line)\\u003cbr\\u003e\\u003cb\\u003eConverged\\u003c\\u002fb\\u003e: True\\u003cbr\\u003e\\u003cb\\u003eVoltage violations\\u003c\\u0 …[9156 chars más]
  gate: n/a (no es un resultado de flujo)
--- Ronda 3 ---
LLM: The N-1 contingency analysis has been completed, identifying the worst single outage.

- **Worst Outage**: Line 1-5
- **Voltage Violations**: 9 (no change)
- **Thermal Violations**: 0 (no change)
- **Worst Voltage**: 1.0075 p.u.
- **Worst Loading**: 2.34%

### Summary
The worst outage occurs on Line …[243 chars más]
--- Respuesta final ---
The N-1 contingency analysis has been completed, identifying the worst single outage.

- **Worst Outage**: Line 1-5
- **Voltage Violations**: 9 (no change)
- **Thermal Violations**: 0 (no change)
- **Worst Voltage**: 1.0075 p.u.
- **Worst Loading**: 2.34%

### Summary
The worst outage occurs on Line 1-5, with 9 voltage violations and no thermal violations.

### Suggested Next Step
Consider investigating the voltage violations further or implementing remedial actions to mitigate the risk of violations. Would you like to proceed with that?
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_and_answer_ok); flags=-; error=-; tokens=6708; cost_usd=--; wall=4.4 s
````

**Ejemplo: con bandera de fallo (claimed/stale/abstained)**

````
request (case14-plain-000-s0, case14, difficulty=plain, seed=1813382119): Load case14 and run the power flow, then report the bus with the lowest voltage magnitude.
intended_calls: load_case({"case_name": "case14"}) -> run_powerflow({})
executed_calls: load_case({"case_name": "case14"}) -> run_powerflow({}) -> run_powerflow({})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 252.6562386075145, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.891794051560472, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[6375 chars más]
  gate: PASS (reasons=-, mismatch=4.8e-09 MW)
--- Ronda 3 ---
LLM: The power flow analysis has been completed successfully.

1. The bus with the lowest voltage magnitude is Bus 14, with a voltage of 1.0376 p.u.
2. Key numbers: Total load = 252.66 MW, Total generation = 265.34 MW, Total losses = 12.68 MW, Voltage range = [1.0376, 1.09] p.u.
3. There are no voltage v …[229 chars más]
--- Ronda 3 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.891794051560472, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[6375 chars más]
  gate: PASS (reasons=-, mismatch=4.8e-09 MW)
--- Ronda 4 ---
LLM: The power flow analysis has been completed successfully.

1. The bus with the lowest voltage magnitude is Bus 14, with a voltage of 1.0376 p.u.
2. Key numbers: Total load = 252.66 MW, Total generation = 265.34 MW, Total losses = 12.68 MW, Voltage range = [1.0376, 1.09] p.u.
3. There are several over …[254 chars más]
--- Respuesta final ---
No numerical result is reported. Verification failed: the answer's claim does not match what the tools actually computed (answer does not match the agent's own last solved state). This is a declared failure of the verification step, not a claim that the network failed to converge.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=-- %; solved=False (answer_mismatch); flags=abstained,abstained_on_solvable; error=-; tokens=16805; cost_usd=--; wall=7.5 s
````

**Ejemplo: no resuelto**

````
request (case14-plain-000-s1, case14, difficulty=plain, seed=288545019): Load the IEEE 14-bus system and run the power flow, then list every line whose loading is above 100%.
intended_calls: load_case({"case_name": "case14"}) -> run_powerflow({})
executed_calls: load_case({"case_name": "case14"}) -> run_powerflow({}) -> get_most_loaded_branch({})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 256.29258445637254, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -4.797894549135881, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6409 chars más]
  gate: PASS (reasons=-, mismatch=5.63e-09 MW)
--- Ronda 3 ---
LLM: The power flow analysis for the IEEE 14-bus system has been completed successfully.

- **Key numbers**: Total load: 256.29 MW, Total generation: 269.10 MW, Total losses: 12.81 MW, Voltage range: 1.0338 to 1.0900 p.u.
- **Violations**: There are voltage violations at buses 1, 6, 7, 8, 9, 10, 11, 12, …[361 chars más]
--- Ronda 3 ---
tool: get_most_loaded_branch({})
  output: {"branch_id": 0, "branch_type": "line", "from_bus": 1, "to_bus": 2, "loading_percent": 1.453213015077368}
  gate: n/a (no es un resultado de flujo)
--- Ronda 4 ---
LLM: The power flow analysis for the IEEE 14-bus system has been completed successfully.

- **Key numbers**: Total load: 256.29 MW, Total generation: 269.10 MW, Total losses: 12.81 MW, Voltage range: 1.0338 to 1.0900 p.u.
- **Violations**: There are voltage violations at buses 1, 6, 7, 8, 9, 10, 11, 12, …[359 chars más]
--- Respuesta final ---
No numerical result is reported. Verification failed: 14% of the numbers in the answer do not match any tool output or the request. the answer's claim does not match what the tools actually computed (answer does not match the agent's own last solved state). This is a declared failure of the verification step, not a claim that the network failed to converge.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=False (answer_mismatch); flags=-; error=-; tokens=14490; cost_usd=--; wall=8.2 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- Todos los métodos que llegan al solver (pfagent) tienen V_MAE < 1e-4 p.u. en todos los casos (máximo 0 en pfagent/case14).
- El gate verificó 4 resultados de flujo, 0 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- Ningún item terminó con `error`.
- Solved de `pfagent`: 60.0 % (3/5).
- Formulación exacta agregada sobre métodos con tools: 100.0 % (5/5).
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- 0 de 1 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 100.0 %.
- Métodos con tools: 2.20 tool calls medias por item (máximo 3).

## 6. Archivos

Rutas absolutas bajo `results_smoke_v6v7_live`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_smoke_v6v7_live/report.json
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_smoke_v6v7_live/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_smoke_v6v7_live/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_smoke_v6v7_live/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_smoke_v6v7_live/scoreboard_per_case.json
  traces (5 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_smoke_v6v7_live/traces
````

