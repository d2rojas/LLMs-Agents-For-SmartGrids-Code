# Informe de experimento: `case14`

Generado el 2026-09-21 13:27 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio case14 (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/single_call_structured/case14
````

- Reports leídos: 1 (`report.rescored.json` usado en 1; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-5.6-sol`
- Métodos: `single_call:structured`
- Casos: `case14`
- Requests: generadas, N=40 por caso y seed, difficulties=todas (1 report)
- Items por dificultad: plain=10, parameterized=10, multistep=10, ambiguous=10
- System prompt: hash `23e5d9b407f9` (40 filas)
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-21 08:12
- Costo total: 0.4731 USD (40 items; costo medio 0.01183 USD/item)
- Items totales: 40; ok=40; con error=0; tokens totales=192180
- Solved global: 10.0 % (4/40)

Errores por tipo:

_(ningún item con `error`)_


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo. **Esta reconstrucción es ilustrativa, no histórica**: usa el código de `llm/prompts.py` de HOY, así que si el texto del prompt cambió después de que esta corrida se generó, lo que se ve aquí no es lo que el modelo recibió. El registro histórico real es el hash por fila (`system_prompt_hash`, ver sección 1 / `benchmarks/experiment_report.py::section_what_ran`), fijado en el momento de la corrida y nunca recalculado.

### Método `single_call:structured` (system_prompt_hash real de esta fila: `23e5d9b407f9`)

**System prompt** (reconstrucción con el código actual, no necesariamente histórica) — 1879 caracteres; strategy=structured; la red ya está cargada (preload_case)

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

## Single-call mode
You are evaluated in single-call mode: the network named in the user message is already loaded. Read the request, decide which tools to call and with which arguments, and emit all tool calls in this one response. Do not ask clarifying questions, do not plan across turns, and do not fabricate numbers.
````

**User prompt (primer item)** — 3821 caracteres; case=case14, seed=1911784258, k=1, request_id=case14-ambiguous-003-s0

````
The network case14 is loaded. Use the tools to fulfil the request below.

## System Data (compact, full case)
Case case14: 14 buses, 15 lines, 5 transformers, total load 253.8 MW. Bus ids are IEEE display ids (1..N); line_id is the net.line row index, transformers use 100000+row index.

### Buses
bus 1 | 135 kV | slack/reference vm 1.06 pu
bus 2 | 135 kV | load 21.47 MW 12.57 Mvar | gen 41.63 MW vm 1.045 pu
bus 3 | 135 kV | load 85.73 MW 17.29 Mvar | gen 0 MW vm 1.01 pu
bus 4 | 135 kV | load 45.57 MW -3.718 Mvar
bus 5 | 135 kV | load 6.887 MW 1.45 Mvar
bus 6 | 0.208 kV | load 11.74 MW 7.862 Mvar | gen 0 MW vm 1.07 pu
bus 7 | 14 kV
bus 8 | 12 kV | gen 0 MW vm 1.09 pu
bus 9 | 0.208 kV | load 32.23 MW 18.14 Mvar
bus 10 | 0.208 kV | load 9.715 MW 6.261 Mvar
bus 11 | 0.208 kV | load 3.424 MW 1.761 Mvar
bus 12 | 0.208 kV | load 6.54 MW 1.715 Mvar
… (2 líneas omitidas de 14)

### Branches
line 0 | 1-2 | r 3.532 x 10.78 ohm/km | len 1 km | max_i 42.34 kA
line 1 | 1-5 | r 9.847 x 40.65 ohm/km | len 1 km | max_i 42.34 kA
line 2 | 2-3 | r 8.564 x 36.08 ohm/km | len 1 km | max_i 42.34 kA
line 3 | 2-4 | r 10.59 x 32.13 ohm/km | len 1 km | max_i 42.34 kA
line 4 | 2-5 | r 10.38 x 31.69 ohm/km | len 1 km | max_i 42.34 kA
line 5 | 3-4 | r 12.21 x 31.17 ohm/km | len 1 km | max_i 42.34 kA
line 6 | 4-5 | r 2.433 x 7.675 ohm/km | len 1 km | max_i 42.34 kA
line 7 | 6-11 | r 4.109e-05 x 8.605e-05 ohm/km | len 1 km | max_i 2.748e+04 kA
line 8 | 6-12 | r 5.318e-05 x 0.0001107 ohm/km | len 1 km | max_i 2.748e+04 kA
line 9 | 6-13 | r 2.862e-05 x 5.636e-05 ohm/km | len 1 km | max_i 2.748e+04 kA
line 10 | 9-10 | r 1.376e-05 x 3.656e-05 ohm/km | len 1 km | max_i 2.748e+04 kA
line 11 | 9-14 | r 5.499e-05 x 0.000117 ohm/km | len 1 km | max_i 2.748e+04 kA
… (8 líneas omitidas de 20)

### Available tools
- load_case(case_name): Load IEEE test case.
- run_powerflow(no arguments): Run power flow on current case.
- modify_load(bus_id, p_mw, q_mvar): Modify bus load and recompute.
- disconnect_line(from_bus, to_bus): Disconnect line/branch between two buses and recompute.
- reconnect_line(from_bus, to_bus): Reconnect line/branch between two buses and recompute.
- get_most_loaded_branch(no arguments): Get most loaded branch.
- run_n1_contingency(top_k, criteria, max_candidates): Run N-1 contingency analysis.
- recommend_remedial_actions(max_actions, allow_load_shed, allow_voltage_control, include_best_comparison): Recommend remedial actions.
- apply_remedial_action(action_index, confirmed): Apply one remedial action by index.
- get_status(no arguments): Get current network status.
- generate_plot(plot_type): Generate one plot.

## Task
Load case14 and disconnect the line between bus ten and bus eleven.

## Output Requirements
Answer by emitting tool calls (function calling) in THIS single response:
- Use only the provided tools, with their exact names and argument names.
- Emit every tool call the request needs, in execution order, in one round; there is no second turn and no memory of earlier turns.
- bus_id / from_bus / to_bus are IEEE display ids (1..N), as printed in the system data.
- Never invent numerical results; numbers come only from tool outputs.
- If the request needs a case other than the loaded one, call load_case first.
````

**FINAL_ANSWER_INSTRUCTION (ronda final)** — 158 caracteres; se añade como mensaje de usuario antes de la respuesta final

````
Write the final answer for the user strictly from the tool outputs above. Never invent numbers; if a tool reported an error or a non-converged result, say so.
````


## 3. Resultados agregados

Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`), en los 4 grupos de `metricas_pfagent_definiciones.md`: **utilidad de tarea** Form. (formulación exacta de las tool calls), V_MAE (p.u., solo sobre peticiones con formulación exacta -- toda fila con herramientas que llega al solver con la formulación correcta da exactamente cero, ver benchmarks/scoring.py) y F_MAE (MW) sobre los items con resultado, Solved (respondió correctamente de extremo a extremo); **corrección solver-grounded** Solver status (convergencia reportada = convergencia real), B_mean (residual medio de KCL de los flujos reportados, MW); **fidelidad** Faith. (por respuesta, no por número: fracción de respuestas donde todo número es trazable a una salida de tool Y viene del solve posterior al último cambio de red) y SFR (fallos declarados con seguridad); **costo** Calls (tool calls medias) y Tok. (tokens medios). Fuera de los 4 grupos, solo en este reporte (no en las tablas del paper): Claim (éxito reclamado sobre un fallo), Escalated y Wrong (silent). Escalated y Wrong (silent) junto con solved_autonomously_rate (no la columna Solved de arriba, que puede solaparse con Escalated -- una abstención de verificación puede caer sobre un item cuyo cálculo de fondo sí era correcto) suman 100 %: dónde termina cada petición -- resuelta sola, entregada a una persona, o mal contestada sin aviso; solo cuenta como Escalated una arquitectura con mecanismo de traspaso real, ver benchmarks.scoring.escalation_check) y $ (costo total USD). Porcentajes en %.

### Por método × caso

| Method | Case | N | Form. | V_MAE solved | V_MAE all | B_mean solved | B_mean all | Solved | Escalated | Wrong-unflagged | Traceable | Tokens | Time (s) | Claim | Escalated | Wrong (silent) | $ |
|---------------------------|------|----|-------------|---------------|---------|----------------|----------|-------------|----------|------------------|---------|------|--------|-----|----------|-----------------|------|
| single_call:structured | case14 | 40 | 20.0 (8/40) | 0 | 1.77e-03 | 0 | 4.79e-02 | 10.0 (4/40) | 0.0 (0/40) | 90.0 | 92.5 | 4804 | 11.22 | -- | 0.0 (0/40) | 90.0 (36/40) | 0.4731 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|---------------------------|-------------|----------------|----------|----------|
| single_call:structured | 60.0 (6/10) | 20.0 (2/10) | 0.0 (0/10) | 0.0 (0/10) |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|---------------------------|-------------|----------------|----------|----------|
| single_call:structured | 30.0 (3/10) | 10.0 (1/10) | 0.0 (0/10) | 0.0 (0/10) |

### Tipos de error de formulación (conteo de items)

| Method | missed_step | ok |
|---------------------------|-------------|----|
| single_call:structured | 32 | 8 |

### Errores de ejecución por método (conteo de items con `error`)

_(ningún item con `error`)_


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `single_call:structured`

**Ejemplo: resuelto (solved=True)**

````
request (case14-parameterized-037-s0, case14, difficulty=parameterized, seed=1292574852): Load the IEEE 14-bus system and run the power flow, then list every line whose loading is above 100%.
intended_calls: load_case({"case_name": "case14"}) -> run_powerflow({})
executed_calls: load_case({"case_name": "case14"})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 262.9675788776612, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 [final] ---
LLM: The IEEE 14-bus case was loaded successfully, but no power-flow result was returned, so overloaded lines cannot be identified.

**Key numbers**
- Total load: **262.9676 MW**
- Total generation capacity: **772.4 MW**
- Total generation, losses, and voltage range: **Not available**

**Violations**
- C …[194 chars más]
--- Respuesta final ---
The IEEE 14-bus case was loaded successfully, but no power-flow result was returned, so overloaded lines cannot be identified.

**Key numbers**
- Total load: **262.9676 MW**
- Total generation capacity: **772.4 MW**
- Total generation, losses, and voltage range: **Not available**

**Violations**
- Cannot determine which lines exceed **100% loading** because the power flow was not run.

**Suggested next step**
- Run the AC power flow, then query branch loadings to list all lines above 100%.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_and_answer_ok); flags=-; error=-; tokens=4798; cost_usd=0.0119; wall=12.9 s
````

**Ejemplo: formulación fallida (formulation_exact=False)**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: load_case({"case_name": "case14"})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 253.84578240591338, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 [final] ---
LLM: 1. **Summary:** case14 was loaded successfully, but the requested line disconnection between buses 10 and 11 was not executed.

2. **Key numbers:** 14 buses, 5 generators, 20 branches, 11 loads; total load **253.8458 MW**; generation capacity **772.4 MW**. Power-flow generation, losses, and voltage …[213 chars más]
--- Respuesta final ---
1. **Summary:** case14 was loaded successfully, but the requested line disconnection between buses 10 and 11 was not executed.

2. **Key numbers:** 14 buses, 5 generators, 20 branches, 11 loads; total load **253.8458 MW**; generation capacity **772.4 MW**. Power-flow generation, losses, and voltage range were not available.

3. **Violations:** Not assessed because no post-disconnection power flow was run.

4. **Suggested next step:** Disconnect the branch between buses 10 and 11 and recompute the power flow.
--- Scoring ---
formulation=missed_step (exact=False); V_MAE=2.05e-03; F_MAE=1.39; faithful=100.0 %; solved=False (formulation); flags=-; error=-; tokens=4732; cost_usd=0.0114; wall=8.0 s
````

**Ejemplo: no resuelto**

````
request (case14-ambiguous-007-s0, case14, difficulty=ambiguous, seed=2073320062): Load the 14-bus test case (case14) and disconnect the line between bus 6 and bus 13 (1-based).
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 6, "to_bus": 13})
executed_calls: load_case({"case_name": "case14"})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 261.9028323717408, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 [final] ---
LLM: 1. **Summary:** The case14 network was loaded successfully, but the requested 6–13 line disconnection was not executed.

2. **Key numbers:** Total load: **261.9028323717408 MW**; generation capacity: **772.4000000000001 MW**. Actual generation, losses, and voltage range were not provided.

3. **Viol …[193 chars más]
--- Respuesta final ---
1. **Summary:** The case14 network was loaded successfully, but the requested 6–13 line disconnection was not executed.

2. **Key numbers:** Total load: **261.9028323717408 MW**; generation capacity: **772.4000000000001 MW**. Actual generation, losses, and voltage range were not provided.

3. **Violations:** Not evaluated because no post-disconnection power flow result is available.

4. **Suggested next step:** Disconnect the branch between buses **6 and 13** and recompute the power flow.
--- Scoring ---
formulation=missed_step (exact=False); V_MAE=8.99e-03; F_MAE=3.80; faithful=100.0 %; solved=False (formulation); flags=-; error=-; tokens=4805; cost_usd=0.0119; wall=11.9 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- V_MAE >= 1e-4 p.u. en 1 filas método×caso con solver: single_call:structured/case14 (1.77e-03).
- El gate no verificó ningún resultado de flujo (gate_checked=0 en todos los items).
- Ningún item terminó con `error`.
- Solved de `single_call:structured`: 10.0 % (4/40).
- Formulación exacta agregada sobre métodos con tools: 20.0 % (8/40).
- Formulación por dificultad: mejor `plain` 60.0 % (6/10), peor `multistep` 0.0 % (0/10).
- Errores de formulación más frecuentes: `missed_step`=32.
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- Trazabilidad de números (Faith.) media con tools: 98.0 %.
- Costo total 0.4731 USD; el método más caro fue `single_call:structured` con 0.4731 USD (100 %).
- Métodos con tools: 1.00 tool calls medias por item (máximo 1).

## 6. Archivos

Rutas absolutas bajo `case14`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/single_call_structured/case14/report.json   [leído: report.rescored.json]
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/single_call_structured/case14/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/single_call_structured/case14/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/single_call_structured/case14/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/single_call_structured/case14/scoreboard_per_case.json
  scoreboard.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/single_call_structured/case14/scoreboard.rescored.json
  scoreboard_per_case.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/single_call_structured/case14/scoreboard_per_case.rescored.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/single_call_structured/case14/traces
  log: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_sol_n40_clean/single_call_structured/case14/run.attempt1.log
````

