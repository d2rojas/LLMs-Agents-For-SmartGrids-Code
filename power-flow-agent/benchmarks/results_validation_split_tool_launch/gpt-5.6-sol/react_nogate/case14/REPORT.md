# Informe de experimento: `case14`

Generado el 2026-09-21 14:45 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio case14 (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-5.6-sol/react_nogate/case14
````

- Reports leídos: 1 (`report.rescored.json` usado en 1; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-5.6-sol`
- Métodos: `react_nogate`
- Casos: `case14`
- Requests: generadas, N=40 por caso y seed, difficulties=todas (1 report)
- Items por dificultad: plain=10, parameterized=10, multistep=10, ambiguous=10
- System prompt: hash `7da5e2a37ec4` (40 filas)
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-21 14:37
- Costo total: 0.0000 USD (40 items; costo medio 0.00000 USD/item)
- Items totales: 40; ok=40; con error=0; tokens totales=535389
- Solved global: 97.5 % (39/40)

Errores por tipo:

_(ningún item con `error`)_


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo. **Esta reconstrucción es ilustrativa, no histórica**: usa el código de `llm/prompts.py` de HOY, así que si el texto del prompt cambió después de que esta corrida se generó, lo que se ve aquí no es lo que el modelo recibió. El registro histórico real es el hash por fila (`system_prompt_hash`, ver sección 1 / `benchmarks/experiment_report.py::section_what_ran`), fijado en el momento de la corrida y nunca recalculado.

### Método `react_nogate` (system_prompt_hash real de esta fila: `7da5e2a37ec4`)

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
|---------------|------|----|---------------|---------------|---------|----------------|----------|---------------|----------|------------------|---------|------|--------|-----|----------|-----------------|----|
| react_nogate | case14 | 40 | 97.5 (39/40) | 0 | 0 | 0 | 0 | 97.5 (39/40) | 0.0 (0/40) | 2.5 | 97.5 | 13385 | 11.49 | -- | 0.0 (0/40) | 2.5 (1/40) | -- |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|---------------|-------------|----------------|----------------|----------------|
| react_nogate | 90.0 (9/10) | 100.0 (10/10) | 100.0 (10/10) | 100.0 (10/10) |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|---------------|-------------|----------------|----------------|----------------|
| react_nogate | 90.0 (9/10) | 100.0 (10/10) | 100.0 (10/10) | 100.0 (10/10) |

### Tipos de error de formulación (conteo de items)

| Method | extra_step | ok |
|---------------|----------|----|
| react_nogate | 1 | 39 |

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
--- Ronda 2 ---
tool: disconnect_line({"from_bus": 10, "to_bus": 11})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.782856812869876, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5930 chars más]
  gate: PASS (reasons=-, mismatch=7.85e-09 MW)
--- Ronda 3 ---
LLM: The IEEE 14-bus case was loaded, line 10–11 disconnected, and the AC power flow converged successfully.

**Key numbers**
- Total load: **253.846 MW**
- Total generation: **266.510 MW**
- Total losses: **12.665 MW**
- Voltage range: **1.010–1.090 p.u.**

**Violations**
- Overvoltage at buses **1, 6, …[194 chars más]
--- Respuesta final ---
The IEEE 14-bus case was loaded, line 10–11 disconnected, and the AC power flow converged successfully.

**Key numbers**
- Total load: **253.846 MW**
- Total generation: **266.510 MW**
- Total losses: **12.665 MW**
- Voltage range: **1.010–1.090 p.u.**

**Violations**
- Overvoltage at buses **1, 6, 7, 8, 11, and 12**
- No thermal violations

**Suggested next step**
Evaluate voltage-control remedial actions, particularly near buses 6–12, or reconnect line 10–11 to restore the base topology.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_and_answer_ok); flags=-; error=-; tokens=5802; cost_usd=--; wall=7.8 s
````

**Ejemplo: formulación fallida (formulation_exact=False)**

````
request (case14-plain-004-s0, case14, difficulty=plain, seed=903170603): Load case14 and run an N-1 contingency analysis and report the worst single outage.
intended_calls: load_case({"case_name": "case14"}) -> run_n1_contingency({})
executed_calls: load_case({"case_name": "case14"}) -> run_n1_contingency({"top_k": 1, "criteria": "max_violations", "max_candidates": 0}) -> get_status({}) -> run_powerflow({}) -> disconnect_line({"from_bus": 1, "to_bus": 5}) -> reconnect_line({"from_bus": 1, "to_bus": 5})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 261.9932169620855, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: run_n1_contingency({"top_k": 1, "criteria": "max_violations", "max_candidates": 0})
  output: {"plot_type": "n1_ranking", "figure_json": "{\"data\":[{\"cliponaxis\":false,\"hoverinfo\":\"text\",\"hovertext\":[\"\\u003cb\\u003eOutage\\u003c\\u002fb\\u003e: 1-5 (line)\\u003cbr\\u003e\\u003cb\\u003eConverged\\u003c\\u002fb\\u003e: True\\u003cbr\\u003e\\u003cb\\u003eVoltage violations\\u003c\\u0 …[9156 chars más]
  gate: n/a (no es un resultado de flujo)
--- Ronda 3 ---
tool: get_status({})
  output: {"active_case": "case14", "network_info": {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 261.9932169620855, "total_gen_capacity_mw": 772.4000000000001}, "has_last_result": false}
  gate: n/a (no es un resultado de flujo)
--- Ronda 4 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -5.12793878696546, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu …[6435 chars más]
  gate: PASS (reasons=-, mismatch=4.7e-09 MW)
--- Ronda 5 ---
tool: disconnect_line({"from_bus": 1, "to_bus": 5})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000004, "va_deg": -7.875088276323269, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6329 chars más]
  gate: PASS (reasons=-, mismatch=2.03e-08 MW)
--- Ronda 6 ---
tool: reconnect_line({"from_bus": 1, "to_bus": 5})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -5.12793878696546, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu …[6435 chars más]
  gate: PASS (reasons=-, mismatch=4.7e-09 MW)
--- Ronda 7 ---
LLM: The worst N-1 contingency, ranked by maximum violations across all 20 branches, is the outage of line **1–5**; the AC power flow converged.

**Key numbers for the outage state**
- Total load: **261.993 MW**
- Total generation: **283.572 MW**
- Total active-power losses: **21.579 MW**
- Voltage range …[427 chars más]
--- Respuesta final ---
The worst N-1 contingency, ranked by maximum violations across all 20 branches, is the outage of line **1–5**; the AC power flow converged.

**Key numbers for the outage state**
- Total load: **261.993 MW**
- Total generation: **283.572 MW**
- Total active-power losses: **21.579 MW**
- Voltage range: **1.0075–1.0900 p.u.**
- Highest branch loading: **2.362%** on line **1–2**

**Violations**
- **9 voltage violations**, all overvoltages; **no increase from the base case**
- **0 thermal violations**
- No new violations caused by this outage

**Suggested next step:** Review voltage-control settings to address the nine pre-existing overvoltages; the disconnected line has been restored to return case14 to its base topology.
--- Scoring ---
formulation=extra_step (exact=False); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=False (formulation); flags=stale_state; error=-; tokens=42523; cost_usd=--; wall=23.8 s
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
LLM: The IEEE 14-bus case was loaded, line 6–13 disconnected, and the AC power flow converged successfully.

**Key numbers**
- Total load: **261.903 MW**
- Total generation: **276.663 MW**
- Total losses: **14.761 MW**
- Voltage range: **0.9989–1.0900 p.u.** (buses 13 and 8)

**Violations**
- Overvoltage …[274 chars más]
--- Respuesta final ---
The IEEE 14-bus case was loaded, line 6–13 disconnected, and the AC power flow converged successfully.

**Key numbers**
- Total load: **261.903 MW**
- Total generation: **276.663 MW**
- Total losses: **14.761 MW**
- Voltage range: **0.9989–1.0900 p.u.** (buses 13 and 8)

**Violations**
- Overvoltages: bus 1 (**1.060 p.u.**), bus 6 (**1.070 p.u.**), bus 7 (**1.0572 p.u.**), bus 8 (**1.090 p.u.**), and bus 11 (**1.0531 p.u.**)
- Thermal violations: **none**

**Suggested next step:** Evaluate remedial voltage-control actions or compare this state with the intact network.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_and_answer_ok); flags=-; error=-; tokens=5810; cost_usd=--; wall=6.6 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- Todos los métodos que llegan al solver (react_nogate) tienen V_MAE < 1e-4 p.u. en todos los casos (máximo 0 en react_nogate/case14).
- El gate verificó 58 resultados de flujo, 0 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- Ningún item terminó con `error`.
- Solved de `react_nogate`: 97.5 % (39/40).
- Formulación exacta agregada sobre métodos con tools: 97.5 % (39/40).
- Formulación por dificultad: mejor `parameterized` 100.0 % (10/10), peor `plain` 90.0 % (9/10).
- Errores de formulación más frecuentes: `extra_step`=1.
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- 1 de 16 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 100.0 %.
- Métodos con tools: 2.75 tool calls medias por item (máximo 6).

## 6. Archivos

Rutas absolutas bajo `case14`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-5.6-sol/react_nogate/case14/report.json   [leído: report.rescored.json]
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-5.6-sol/react_nogate/case14/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-5.6-sol/react_nogate/case14/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-5.6-sol/react_nogate/case14/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-5.6-sol/react_nogate/case14/scoreboard_per_case.json
  scoreboard.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-5.6-sol/react_nogate/case14/scoreboard.rescored.json
  scoreboard_per_case.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-5.6-sol/react_nogate/case14/scoreboard_per_case.rescored.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_split_tool_launch/gpt-5.6-sol/react_nogate/case14/traces
````

