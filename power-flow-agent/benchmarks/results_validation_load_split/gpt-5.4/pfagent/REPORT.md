# Informe de experimento: `pfagent`

Generado el 2026-09-18 22:46 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio pfagent (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_load_split/gpt-5.4/pfagent
````

- Reports leídos: 1 (`report.rescored.json` usado en 1; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-5.4`
- Métodos: `pfagent`
- Casos: `case14`
- Requests: generadas, N=40 por caso y seed, difficulties=todas (1 report)
- Items por dificultad: plain=10, parameterized=10, multistep=10, ambiguous=10
- System prompt: hash `7da5e2a37ec4` (40 filas)
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-18 21:56
- Costo total: 1.5285 USD (40 items; costo medio 0.03821 USD/item)
- Items totales: 40; ok=40; con error=0; tokens totales=539013
- Solved global: 100.0 % (40/40)

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

**User prompt (primer item) = request_text** — 67 caracteres; case=case14, seed=1911784258, k=1, request_id=case14-ambiguous-003-s0

````
Load case14 and disconnect the line between bus ten and bus eleven.
````


## 3. Resultados agregados

Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`), en los 4 grupos de `metricas_pfagent_definiciones.md`: **utilidad de tarea** Form. (formulación exacta de las tool calls), V_MAE (p.u., solo sobre peticiones con formulación exacta -- toda fila con herramientas que llega al solver con la formulación correcta da exactamente cero, ver benchmarks/scoring.py) y F_MAE (MW) sobre los items con resultado, Solved (respondió correctamente de extremo a extremo); **corrección solver-grounded** Solver status (convergencia reportada = convergencia real), B_mean (residual medio de KCL de los flujos reportados, MW); **fidelidad** Faith. (por respuesta, no por número: fracción de respuestas donde todo número es trazable a una salida de tool Y viene del solve posterior al último cambio de red) y SFR (fallos declarados con seguridad); **costo** Calls (tool calls medias) y Tok. (tokens medios). Fuera de los 4 grupos, solo en este reporte (no en las tablas del paper): Claim (éxito reclamado sobre un fallo), Escalated y Wrong (silent). Escalated y Wrong (silent) junto con solved_autonomously_rate (no la columna Solved de arriba, que puede solaparse con Escalated -- una abstención de verificación puede caer sobre un item cuyo cálculo de fondo sí era correcto) suman 100 %: dónde termina cada petición -- resuelta sola, entregada a una persona, o mal contestada sin aviso; solo cuenta como Escalated una arquitectura con mecanismo de traspaso real, ver benchmarks.scoring.escalation_check) y $ (costo total USD). Porcentajes en %.

### Por método × caso

| Method | Case | N | Form. | V_MAE | F_MAE | Solved | Solver status | B_mean | Faith. | SFR | Calls | Tok. | Claim | Escalated | Wrong (silent) | $ |
|-------|------|----|----------------|-----|-----|----------------|----------------|------|----------------|----|-----|-----|-----|----------|-----------------|------|
| pfagent | case14 | 40 | 100.0 (40/40) | 0 | 0.00 | 100.0 (40/40) | 100.0 (40/40) | 0 | 100.0 (40/40) | -- | 2.7 | 13475 | -- | 5.0 (2/40) | 0.0 (0/40) | 1.5285 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|-------|----------------|----------------|----------------|----------------|
| pfagent | 100.0 (10/10) | 100.0 (10/10) | 100.0 (10/10) | 100.0 (10/10) |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|-------|----------------|----------------|----------------|----------------|
| pfagent | 100.0 (10/10) | 100.0 (10/10) | 100.0 (10/10) | 100.0 (10/10) |

### Verificación final (pfagent: V(x,c,z,y) aplicado a la respuesta final)

`pass_first` = pasó al primer intento; `pass_retry` = pasó tras el único reintento con el veredicto añadido; `abstained` = falló dos veces, respuesta forzada a fallo declarado sin números; `retry_mutation` = el reintento intentó una herramienta que muta la red (bloqueada, nunca ejecutada; cuenta como abstención) — ver "Integridad del reintento" abajo. N = items con `final_gate` activo (no todos los métodos lo tienen).

| Method | N | pass_first | pass_retry | abstained | retry_mutation |
|-------|----|---------------|----------|----------|-----------------|
| pfagent | 40 | 90.0 (36/40) | 5.0 (2/40) | 5.0 (2/40) | 0.0 (0/40) |


### Integridad del reintento

De 4 ítem(s) que llegaron a un reintento, 0 intentaron una herramienta que muta la red (bloqueada) en vez de corregir el reporte; se cuentan como abstención, no como "pasó". El mensaje de reintento ya no sugiere la corrección específica (p. ej. "reconnect...") y bloquea estructuralmente `modify_load`, `disconnect_line`, `reconnect_line`, `apply_remedial_action` y `load_case` mientras el reintento está en efecto.

### Tipos de error de formulación (conteo de items)

| Method | ok |
|-------|----|
| pfagent | 40 |

### Errores de ejecución por método (conteo de items con `error`)

_(ningún item con `error`)_


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `pfagent`

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
--- Ronda 2 ---
tool: disconnect_line({"from_bus": 10, "to_bus": 11})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.782856812869876, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5930 chars más]
  gate: PASS (reasons=-, mismatch=7.85e-09 MW)
--- Ronda 3 ---
LLM: 1. One-sentence summary: I loaded IEEE case14 and disconnected the line between buses 10 and 11; the post-contingency power flow converged successfully.

2. Key numbers:
- Total load: 253.8458 MW
- Total generation: 266.5103 MW
- Total losses: 12.6645 MW
- Voltage range: 1.0100 to 1.0900 pu

3. Viol …[467 chars más]
--- Respuesta final ---
1. One-sentence summary: I loaded IEEE case14 and disconnected the line between buses 10 and 11; the post-contingency power flow converged successfully.

2. Key numbers:
- Total load: 253.8458 MW
- Total generation: 266.5103 MW
- Total losses: 12.6645 MW
- Voltage range: 1.0100 to 1.0900 pu

3. Violations, if any:
- Voltage violations only; no thermal overloads were reported.
- Overvoltage buses: 1 (1.0600 pu), 6 (1.0700 pu), 7 (1.0573 pu), 8 (1.0900 pu), 11 (1.0636 pu), 12 (1.0536 pu)
- The disconnected line 10–11 now carries 0.0 MW / 0.0 Mvar as expected.

4. Suggested next step:
- If you want, I can check the most loaded remaining branch, run an N-1 contingency analysis from this modified state, or suggest remedial actions for the overvoltage violations.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_ok); flags=-; error=-; tokens=5833; cost_usd=0.0182; wall=11.7 s
````

**Ejemplo: con bandera de fallo (claimed/stale/abstained)**

````
request (case14-multistep-030-s0, case14, difficulty=multistep, seed=537958268): Load case14, set the active load at bus 14 to 17.2 MW, disconnect the line between bus 1 and bus 5, reconnect the line between bus 1 and bus 5, and finally run an N-1 contingency analysis ranked by min voltage and report the 8 worst outages.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 14, "p_mw": 17.2}) -> disconnect_line({"from_bus": 1, "to_bus": 5}) -> reconnect_line({"from_bus": 1, "to_bus": 5}) -> run_n1_contingency({"top_k": 8, "criteria": "min_voltage"})
executed_calls: load_case({"case_name": "case14"}) -> set_active_load({"bus_id": 14, "p_mw": 17.2}) -> disconnect_line({"from_bus": 1, "to_bus": 5}) -> reconnect_line({"from_bus": 1, "to_bus": 5}) -> run_n1_contingency({"top_k": 8, "criteria": "min_voltage", "max_candidates": 0}) -> run_powerflow({})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 271.9322468585065, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: set_active_load({"bus_id": 14, "p_mw": 17.2})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0449999999999997, "va_deg": -5.452601937946843, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6367 chars más]
  gate: PASS (reasons=-, mismatch=6.8e-09 MW)
--- Ronda 3 ---
tool: disconnect_line({"from_bus": 1, "to_bus": 5})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -8.384501830561186, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[6071 chars más]
  gate: PASS (reasons=-, mismatch=2.94e-08 MW)
--- Ronda 4 ---
tool: reconnect_line({"from_bus": 1, "to_bus": 5})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0449999999999997, "va_deg": -5.452601937946843, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6265 chars más]
  gate: PASS (reasons=-, mismatch=6.8e-09 MW)
--- Ronda 5 ---
tool: run_n1_contingency({"top_k": 8, "criteria": "min_voltage", "max_candidates": 0})
  output: {"plot_type": "n1_ranking", "figure_json": "{\"data\":[{\"cliponaxis\":false,\"hoverinfo\":\"text\",\"hovertext\":[\"\\u003cb\\u003eOutage\\u003c\\u002fb\\u003e: 3-4 (line)\\u003cbr\\u003e\\u003cb\\u003eConverged\\u003c\\u002fb\\u003e: True\\u003cbr\\u003e\\u003cb\\u003eVoltage violations\\u003c\\u0 …[19510 chars más]
  gate: n/a (no es un resultado de flujo)
--- Ronda 6 ---
LLM: 1. One-sentence summary

I loaded IEEE case14, changed bus 14 active load to 17.2 MW, temporarily disconnected and then reconnected line 1–5, and finally ran an N-1 contingency analysis on the restored network ranked by minimum voltage for the 8 worst outages.

2. Key numbers

- Final solved base ca …[1828 chars más]
--- Ronda 6 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0449999999999997, "va_deg": -5.452601937946843, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6265 chars más]
  gate: PASS (reasons=-, mismatch=6.8e-09 MW)
--- Ronda 7 ---
LLM: 1. One-sentence summary

I loaded IEEE case14, set bus 14 active load to 17.2 MW, disconnected and then reconnected line 1–5, and the final restored network converged; the N-1 analysis ranked by minimum voltage identifies the 8 worst outages listed below.

2. Key numbers

- Final network state after …[1651 chars más]
--- Respuesta final ---
No numerical result is reported. Verification failed: the answer quotes 1 number(s) from a solve made before the last network change (reconnecting the branch between bus 1 and bus 5). This is a declared failure of the verification step, not a claim that the network failed to converge.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=-- %; solved=True (numeric_ok); flags=abstained,abstained_on_solvable; error=-; tokens=79624; cost_usd=0.2171; wall=39.1 s
````

**Ejemplo: primer item**

````
request (case14-ambiguous-007-s0, case14, difficulty=ambiguous, seed=2073320062): Load the 14-bus test case (case14) and disconnect the line between bus 6 and bus 13 (1-based).
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 6, "to_bus": 13})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 6, "to_bus": 13})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 261.9028323717408, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: disconnect_line({"from_bus": 6, "to_bus": 13})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -5.104476346710827, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5772 chars más]
  gate: PASS (reasons=-, mismatch=5.12e-08 MW)
--- Ronda 3 ---
LLM: 1. Loaded IEEE case14 and disconnected the line between buses 6 and 13; the post-outage power flow converged.

2. Key numbers
- Total load: 261.903 MW
- Total generation: 276.663 MW
- Total losses: 14.761 MW
- Voltage range: 0.9989 to 1.0900 pu

3. Violations, if any
- Voltage violations:
  - Bus 1: …[419 chars más]
--- Respuesta final ---
1. Loaded IEEE case14 and disconnected the line between buses 6 and 13; the post-outage power flow converged.

2. Key numbers
- Total load: 261.903 MW
- Total generation: 276.663 MW
- Total losses: 14.761 MW
- Voltage range: 0.9989 to 1.0900 pu

3. Violations, if any
- Voltage violations:
  - Bus 1: 1.0600 pu overvoltage
  - Bus 6: 1.0700 pu overvoltage
  - Bus 7: 1.0572 pu overvoltage
  - Bus 8: 1.0900 pu overvoltage
  - Bus 11: 1.0531 pu overvoltage
- Thermal violations: none
- Disconnected line status:
  - Line 6–13 flow is now 0.0 MW / 0.0 Mvar

4. Suggested next step
- I can now check the most loaded remaining branch, run an N-1 contingency analysis, or suggest remedial actions for the voltage violations.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_ok); flags=-; error=-; tokens=5811; cost_usd=0.0181; wall=5.7 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- Todos los métodos que llegan al solver (pfagent) tienen V_MAE < 1e-4 p.u. en todos los casos (máximo 0 en pfagent/case14).
- El gate verificó 53 resultados de flujo, 0 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- Ningún item terminó con `error`.
- Solved de `pfagent`: 100.0 % (40/40).
- Formulación exacta agregada sobre métodos con tools: 100.0 % (40/40).
- Formulación por dificultad: mejor `plain` 100.0 % (10/10), peor `plain` 100.0 % (10/10).
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- 0 de 15 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 100.0 %.
- Costo total 1.5285 USD; el método más caro fue `pfagent` con 1.5285 USD (100 %).
- Métodos con tools: 2.70 tool calls medias por item (máximo 6).

## 6. Archivos

Rutas absolutas bajo `pfagent`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_load_split/gpt-5.4/pfagent/report.json   [leído: report.rescored.json]
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_load_split/gpt-5.4/pfagent/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_load_split/gpt-5.4/pfagent/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_load_split/gpt-5.4/pfagent/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_load_split/gpt-5.4/pfagent/scoreboard_per_case.json
  scoreboard.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_load_split/gpt-5.4/pfagent/scoreboard.rescored.json
  scoreboard_per_case.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_load_split/gpt-5.4/pfagent/scoreboard_per_case.rescored.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_load_split/gpt-5.4/pfagent/traces
````

