# Informe de experimento: `case14`

Generado el 2026-09-21 17:29 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio case14 (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-4o-mini/pfagent/case14
````

- Reports leídos: 1 (`report.rescored.json` usado en 1; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-4o-mini`
- Métodos: `pfagent`
- Casos: `case14`
- Requests: generadas, N=40 por caso y seed, difficulties=todas (1 report)
- Items por dificultad: plain=10, parameterized=10, multistep=10, ambiguous=10
- System prompt: hash `7da5e2a37ec4` (40 filas)
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-21 14:37
- Costo total: 0.0000 USD (40 items; costo medio 0.00000 USD/item)
- Items totales: 40; ok=40; con error=0; tokens totales=468541
- Solved global: 70.0 % (28/40)

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

| Method | Case | N | Form. | V_MAE solved | V_MAE all | B_mean solved | B_mean all | Solved | Escalated | Wrong-unflagged | Traceable | Tokens | Time (s) | Claim | Escalated | Wrong (silent) | $ |
|-------|------|----|----------------|---------------|---------|----------------|----------|---------------|---------------|------------------|---------|------|--------|-----|---------------|-----------------|----|
| pfagent | case14 | 40 | 100.0 (40/40) | 0 | 0 | 0 | 0 | 70.0 (28/40) | 30.0 (12/40) | 0.0 | 97.5 | 11714 | 5.79 | -- | 30.0 (12/40) | 0.0 (0/40) | -- |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|-------|----------------|----------------|----------------|----------------|
| pfagent | 100.0 (10/10) | 100.0 (10/10) | 100.0 (10/10) | 100.0 (10/10) |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|-------|-------------|----------------|-------------|----------------|
| pfagent | 80.0 (8/10) | 80.0 (8/10) | 20.0 (2/10) | 100.0 (10/10) |

### Verificación final (pfagent: V(x,c,z,y) aplicado a la respuesta final)

`pass_first` = pasó al primer intento; `pass_retry` = pasó tras el único reintento con el veredicto añadido; `abstained` = falló dos veces, respuesta forzada a fallo declarado sin números; `retry_mutation` = el reintento intentó una herramienta que muta la red (bloqueada, nunca ejecutada; cuenta como abstención) — ver "Integridad del reintento" abajo. N = items con `final_gate` activo (no todos los métodos lo tienen).

| Method | N | pass_first | pass_retry | abstained | retry_mutation |
|-------|----|---------------|----------|---------------|-----------------|
| pfagent | 40 | 70.0 (28/40) | 0.0 (0/40) | 30.0 (12/40) | 0.0 (0/40) |


### Integridad del reintento

De 12 ítem(s) que llegaron a un reintento, 0 intentaron una herramienta que muta la red (bloqueada) en vez de corregir el reporte; se cuentan como abstención, no como "pasó". El mensaje de reintento ya no sugiere la corrección específica (p. ej. "reconnect...") y bloquea estructuralmente `modify_load`, `disconnect_line`, `reconnect_line`, `apply_remedial_action` y `load_case` mientras el reintento está en efecto.

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
tool: disconnect_line({"from_bus": 10, "to_bus": 11})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.782856812869876, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5930 chars más]
  gate: PASS (reasons=-, mismatch=7.85e-09 MW)
--- Ronda 2 ---
LLM: The case 14 has been loaded, and the line between bus 10 and bus 11 has been successfully disconnected.

- **Total Load:** 253.85 MW
- **Total Generation:** 266.51 MW
- **Total Losses:** 12.66 MW
- **Voltage Range:** 1.01 to 1.09 p.u.

**Violations:** There are several overvoltage violations at buse …[162 chars más]
--- Respuesta final ---
The case 14 has been loaded, and the line between bus 10 and bus 11 has been successfully disconnected.

- **Total Load:** 253.85 MW
- **Total Generation:** 266.51 MW
- **Total Losses:** 12.66 MW
- **Voltage Range:** 1.01 to 1.09 p.u.

**Violations:** There are several overvoltage violations at buses 1, 6, 7, 8, 11, and 12.

**Suggested Next Step:** Consider running a contingency analysis to assess the impact of this disconnection on the network's stability.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_and_answer_ok); flags=-; error=-; tokens=4695; cost_usd=--; wall=3.2 s
````

**Ejemplo: con bandera de fallo (claimed/stale/abstained)**

````
request (case14-multistep-002-s0, case14, difficulty=multistep, seed=1627694679): Load the 14-bus test case (case14), disconnect the line between bus 6 and bus 13, disconnect the line between bus 12 and bus 13, and finally rerun the power flow, then list every line whose loading is above 100%.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 6, "to_bus": 13}) -> disconnect_line({"from_bus": 12, "to_bus": 13}) -> run_powerflow({})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 6, "to_bus": 13}) -> disconnect_line({"from_bus": 12, "to_bus": 13}) -> run_powerflow({})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 257.9016499664761, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
tool: disconnect_line({"from_bus": 6, "to_bus": 13})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -5.078737433931405, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.0100000 …[5832 chars más]
  gate: PASS (reasons=-, mismatch=4.88e-08 MW)
tool: disconnect_line({"from_bus": 12, "to_bus": 13})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0449999999999997, "va_deg": -5.117618104783695, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[5729 chars más]
  gate: PASS (reasons=-, mismatch=5.12e-13 MW)
--- Ronda 2 ---
LLM: The power flow analysis has been completed after disconnecting the specified lines.

1. Summary: The power flow converged successfully after the modifications.
2. Key numbers: Total load = 257.90 MW, Total generation = 273.14 MW, Total losses = 15.24 MW, Voltage range = [0.9178, 1.0900] p.u.
3. Viol …[259 chars más]
--- Ronda 2 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0449999999999997, "va_deg": -5.117618104783695, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[5729 chars más]
  gate: PASS (reasons=-, mismatch=5.12e-13 MW)
--- Ronda 3 ---
LLM: The power flow analysis has been re-evaluated after the modifications.

1. Summary: The power flow converged successfully after disconnecting the specified lines.
2. Key numbers: Total load = 257.90 MW, Total generation = 273.14 MW, Total losses = 15.24 MW, Voltage range = [0.9178, 1.0900] p.u.
3. V …[254 chars más]
--- Respuesta final ---
No numerical result is reported. Verification failed: the answer's claim does not match what the tools actually computed (answer does not match the agent's own last solved state). This is a declared failure of the verification step, not a claim that the network failed to converge.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=-- %; solved=False (answer_mismatch); flags=abstained,abstained_on_solvable; error=-; tokens=22585; cost_usd=--; wall=6.9 s
````

**Ejemplo: no resuelto**

````
request (case14-multistep-006-s0, case14, difficulty=multistep, seed=556019486): Load the 14-bus test case (case14), set the active load at bus 4 to 42.7 MW, disconnect the line between bus 3 and bus 4, reconnect the line between bus 3 and bus 4, and finally rerun the power flow, then list every line whose loading is above 80%.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 4, "p_mw": 42.7}) -> disconnect_line({"from_bus": 3, "to_bus": 4}) -> reconnect_line({"from_bus": 3, "to_bus": 4}) -> run_powerflow({})
executed_calls: load_case({"case_name": "case14"}) -> set_active_load({"bus_id": 4, "p_mw": 42.7}) -> disconnect_line({"from_bus": 3, "to_bus": 4}) -> reconnect_line({"from_bus": 3, "to_bus": 4}) -> run_powerflow({})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 251.83093927460206, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: set_active_load({"bus_id": 4, "p_mw": 42.7})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -4.656475614052621, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6482 chars más]
  gate: PASS (reasons=-, mismatch=4.76e-09 MW)
--- Ronda 3 ---
tool: disconnect_line({"from_bus": 3, "to_bus": 4})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.817570053999097, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[6348 chars más]
  gate: PASS (reasons=-, mismatch=2.37e-09 MW)
tool: reconnect_line({"from_bus": 3, "to_bus": 4})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -4.656475614052621, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6381 chars más]
  gate: PASS (reasons=-, mismatch=4.76e-09 MW)
--- Ronda 4 ---
LLM: 1. The power flow analysis has been completed after modifying the load and reconnecting the line between bus 3 and bus 4.
2. Key numbers: Total load = 247.75 MW, Total generation = 259.61 MW, Total losses = 11.86 MW, Voltage range = 1.0099 to 1.0900 p.u.
3. Violations: There are multiple overvoltage …[196 chars más]
--- Ronda 4 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -4.656475614052621, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6381 chars más]
  gate: PASS (reasons=-, mismatch=4.76e-09 MW)
--- Ronda 5 ---
LLM: 1. The power flow analysis has been successfully rerun after the modifications, confirming the current state of the system.
2. Key numbers: Total load = 247.75 MW, Total generation = 259.61 MW, Total losses = 11.86 MW, Voltage range = 1.0099 to 1.0900 p.u.
3. Violations: There are multiple overvolta …[198 chars más]
--- Respuesta final ---
No numerical result is reported. Verification failed: the answer's claim does not match what the tools actually computed (answer does not match the agent's own last solved state). This is a declared failure of the verification step, not a claim that the network failed to converge.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=-- %; solved=False (answer_mismatch); flags=abstained,abstained_on_solvable; error=-; tokens=37544; cost_usd=--; wall=8.2 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- Todos los métodos que llegan al solver (pfagent) tienen V_MAE < 1e-4 p.u. en todos los casos (máximo 0 en pfagent/case14).
- El gate verificó 53 resultados de flujo, 0 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- Ningún item terminó con `error`.
- Solved de `pfagent`: 70.0 % (28/40).
- Formulación exacta agregada sobre métodos con tools: 100.0 % (40/40).
- Formulación por dificultad: mejor `plain` 100.0 % (10/10), peor `plain` 100.0 % (10/10).
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- 0 de 15 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 96.9 %.
- Métodos con tools: 2.60 tool calls medias por item (máximo 5).

## 6. Archivos

Rutas absolutas bajo `case14`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-4o-mini/pfagent/case14/report.json   [leído: report.rescored.json]
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-4o-mini/pfagent/case14/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-4o-mini/pfagent/case14/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-4o-mini/pfagent/case14/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-4o-mini/pfagent/case14/scoreboard_per_case.json
  scoreboard.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-4o-mini/pfagent/case14/scoreboard.rescored.json
  scoreboard_per_case.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-4o-mini/pfagent/case14/scoreboard_per_case.rescored.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-4o-mini/pfagent/case14/traces
````

