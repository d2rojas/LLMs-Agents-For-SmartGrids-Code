# Informe de experimento: `pfagent`

Generado el 2026-09-18 22:00 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio pfagent (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n10/gpt-5.6-sol/pfagent
````

- Reports leídos: 1 (`report.rescored.json` usado en 0; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-5.6-sol`
- Métodos: `pfagent`
- Casos: `case14`
- Requests: generadas, N=10 por caso y seed, difficulties=todas (1 report)
- Items por dificultad: plain=3, parameterized=3, multistep=2, ambiguous=2
- System prompt: hash `7da5e2a37ec4` (10 filas)
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-18 21:26
- Costo total: 0.3174 USD (10 items; costo medio 0.03174 USD/item)
- Items totales: 10; ok=10; con error=0; tokens totales=140334
- Solved global: 80.0 % (8/10)

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
|-------|------|----|-------------|-----|-----|-------------|----------------|--------|----------------|----|-----|-----|-----|----------|-----------------|------|
| pfagent | case14 | 10 | 80.0 (8/10) | 0 | 0.00 | 80.0 (8/10) | 100.0 (10/10) | 7.73e-07 | 100.0 (10/10) | -- | 3.2 | 14033 | -- | 0.0 (0/10) | 20.0 (2/10) | 0.3174 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|-------|----------|----------------|----------|-------------|
| pfagent | 66.7 (2/3) | 100.0 (3/3) | 50.0 (1/2) | 100.0 (2/2) |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|-------|----------|----------------|----------|-------------|
| pfagent | 66.7 (2/3) | 100.0 (3/3) | 50.0 (1/2) | 100.0 (2/2) |

### Verificación final (pfagent: V(x,c,z,y) aplicado a la respuesta final)

`pass_first` = pasó al primer intento; `pass_retry` = pasó tras el único reintento con el veredicto añadido; `abstained` = falló dos veces, respuesta forzada a fallo declarado sin números; `retry_mutation` = el reintento intentó una herramienta que muta la red (bloqueada, nunca ejecutada; cuenta como abstención) — ver "Integridad del reintento" abajo. N = items con `final_gate` activo (no todos los métodos lo tienen).

| Method | N | pass_first | pass_retry | abstained | retry_mutation |
|-------|----|----------------|----------|----------|-----------------|
| pfagent | 10 | 100.0 (10/10) | 0.0 (0/10) | 0.0 (0/10) | 0.0 (0/10) |

### Tipos de error de formulación (conteo de items)

| Method | extra_arg_changes_result | ok |
|-------|------------------------------|----|
| pfagent | 2 | 8 |

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
LLM: The IEEE 14-bus case was loaded, line 10–11 disconnected, and the AC power flow converged successfully.

**Key numbers**
- Total load: **253.846 MW**
- Total generation: **266.510 MW**
- Total losses: **12.665 MW**
- Voltage range: **1.010–1.090 p.u.**

**Violations**
- Overvoltage at buses **1, 6, …[139 chars más]
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

**Suggested next step:** Review voltage-control remedial actions, particularly near buses 6–12.
--- Scoring ---
formulation=ok (exact=True); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=True (numeric_ok); flags=-; error=-; tokens=5418; cost_usd=0.0130; wall=14.6 s
````

**Ejemplo: formulación fallida (formulation_exact=False)**

````
request (case14-multistep-006-s0, case14, difficulty=multistep, seed=556019486): Load the 14-bus test case (case14), set the active load at bus 4 to 42.7 MW, disconnect the line between bus 3 and bus 4, reconnect the line between bus 3 and bus 4, and finally rerun the power flow, then list every line whose loading is above 80%.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 4, "p_mw": 42.7}) -> disconnect_line({"from_bus": 3, "to_bus": 4}) -> reconnect_line({"from_bus": 3, "to_bus": 4}) -> run_powerflow({})
executed_calls: load_case({"case_name": "case14"}) -> get_status({}) -> modify_load({"bus_id": 4, "p_mw": 42.7, "q_mvar": -3.9}) -> disconnect_line({"from_bus": 3, "to_bus": 4}) -> reconnect_line({"from_bus": 3, "to_bus": 4}) -> run_powerflow({})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 251.83093927460206, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: get_status({})
  output: {"active_case": "case14", "network_info": {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 251.83093927460206, "total_gen_capacity_mw": 772.4000000000001}, "has_last_result": false}
  gate: n/a (no es un resultado de flujo)
--- Ronda 3 ---
LLM: I’ll interpret “set the active load” as retaining bus 4’s standard case14 reactive load setting while changing only its active load.
tool: modify_load({"bus_id": 4, "p_mw": 42.7, "q_mvar": -3.9})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0449999999999997, "va_deg": -4.656433439016519, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6396 chars más]
  gate: PASS (reasons=-, mismatch=4.73e-09 MW)
--- Ronda 4 ---
tool: disconnect_line({"from_bus": 3, "to_bus": 4})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.8175291024652545, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.009999 …[6330 chars más]
  gate: PASS (reasons=-, mismatch=2.35e-09 MW)
--- Ronda 5 ---
tool: reconnect_line({"from_bus": 3, "to_bus": 4})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0449999999999997, "va_deg": -4.656433439016519, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6396 chars más]
  gate: PASS (reasons=-, mismatch=4.73e-09 MW)
--- Ronda 6 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0449999999999997, "va_deg": -4.656433439016519, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[6396 chars más]
  gate: PASS (reasons=-, mismatch=4.73e-09 MW)
--- Ronda 7 ---
LLM: The requested sequence completed successfully, and the final AC power flow converged with line 3–4 reconnected.

**Key numbers**
- Total load: **247.749 MW**
- Total generation: **259.607 MW**
- Total active-power losses: **11.858 MW**
- Voltage range: **1.010–1.090 p.u.**
- Bus 4 active load: **42. …[428 chars más]
--- Respuesta final ---
The requested sequence completed successfully, and the final AC power flow converged with line 3–4 reconnected.

**Key numbers**
- Total load: **247.749 MW**
- Total generation: **259.607 MW**
- Total active-power losses: **11.858 MW**
- Voltage range: **1.010–1.090 p.u.**
- Bus 4 active load: **42.7 MW**; reactive load retained at **−3.9 MVAr**

**Lines loaded above 80%**
- **None.**  
  The highest reported loading is line **1–2 at 1.412%**.

**Violations**
- No thermal violations.
- Overvoltage violations at buses **1, 6, 7, 8, 9, 10, 11, 12, and 13**.
- Maximum voltage: **1.090 p.u. at bus 8**.

**Suggested next step**
- Review generator voltage setpoints or run remedial-action analysis to address the overvoltages.
--- Scoring ---
formulation=extra_arg_changes_result (exact=False); V_MAE=8.15e-06; F_MAE=0.00; faithful=100.0 %; solved=False (formulation); flags=-; error=-; tokens=35566; cost_usd=0.0778; wall=26.8 s
````

**Ejemplo: no resuelto**

````
request (case14-plain-008-s0, case14, difficulty=plain, seed=1097954098): Load case14 and set the active load at bus 2 to 21.7 MW.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 2, "p_mw": 21.7})
executed_calls: load_case({"case_name": "case14"}) -> get_status({}) -> modify_load({"bus_id": 2, "p_mw": 21.7, "q_mvar": 12.7})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 255.7577849683521, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: get_status({})
  output: {"active_case": "case14", "network_info": {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 255.7577849683521, "total_gen_capacity_mw": 772.4000000000001}, "has_last_result": false}
  gate: n/a (no es un resultado de flujo)
--- Ronda 3 ---
tool: modify_load({"bus_id": 2, "p_mw": 21.7, "q_mvar": 12.7})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0449999999999997, "va_deg": -4.77901937688733, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu …[6277 chars más]
  gate: PASS (reasons=-, mismatch=6.1e-09 MW)
--- Ronda 4 ---
LLM: 1. **Summary:** IEEE 14-bus case loaded, bus 2 active load set to **21.7 MW**, and the AC power flow converged.

2. **Key numbers:**
   - Total load: **256.540 MW**
   - Total generation: **269.250 MW**
   - Total active-power losses: **12.710 MW**
   - Voltage range: **1.010–1.090 p.u.**

3. **Viol …[237 chars más]
--- Respuesta final ---
1. **Summary:** IEEE 14-bus case loaded, bus 2 active load set to **21.7 MW**, and the AC power flow converged.

2. **Key numbers:**
   - Total load: **256.540 MW**
   - Total generation: **269.250 MW**
   - Total active-power losses: **12.710 MW**
   - Voltage range: **1.010–1.090 p.u.**

3. **Violations:**
   - Overvoltages at buses **1, 6, 7, 8, 9, 11, 12, and 13**
   - No thermal violations

4. **Suggested next step:** Review voltage-control adjustments, particularly around bus 8, which has the highest voltage at **1.090 p.u.**
--- Scoring ---
formulation=extra_arg_changes_result (exact=False); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=False (formulation); flags=-; error=-; tokens=6994; cost_usd=0.0184; wall=17.8 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- Todos los métodos que llegan al solver (pfagent) tienen V_MAE < 1e-4 p.u. en todos los casos (máximo 8.15e-07 en pfagent/case14).
- El gate verificó 15 resultados de flujo, 0 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- Ningún item terminó con `error`.
- Solved de `pfagent`: 80.0 % (8/10).
- Formulación exacta agregada sobre métodos con tools: 80.0 % (8/10).
- Formulación por dificultad: mejor `parameterized` 100.0 % (3/3), peor `multistep` 50.0 % (1/2).
- Errores de formulación más frecuentes: `extra_arg_changes_result`=2.
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- 0 de 6 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 100.0 %.
- Costo total 0.3174 USD; el método más caro fue `pfagent` con 0.3174 USD (100 %).
- Métodos con tools: 3.20 tool calls medias por item (máximo 6).

## 6. Archivos

Rutas absolutas bajo `pfagent`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n10/gpt-5.6-sol/pfagent/report.json
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n10/gpt-5.6-sol/pfagent/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n10/gpt-5.6-sol/pfagent/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n10/gpt-5.6-sol/pfagent/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n10/gpt-5.6-sol/pfagent/scoreboard_per_case.json
  traces (10 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_n10/gpt-5.6-sol/pfagent/traces
````

