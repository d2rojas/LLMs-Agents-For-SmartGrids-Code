# Informe de experimento: `results_validation_gpt-4o-mini_stress`

Generado el 2026-09-21 12:24 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio results_validation_gpt-4o-mini_stress (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-4o-mini_stress
````

- Reports leídos: 1 (`report.rescored.json` usado en 1; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-4o-mini`
- Métodos: `pfagent`
- Casos: `case14`
- Requests: generadas, N=40 por caso y seed, difficulties=['stress'] (1 report)
- Items por dificultad: stress=40
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-16 10:44
- Costo total: 0.1325 USD (40 items; costo medio 0.00331 USD/item)
- Items totales: 40; ok=40; con error=0; tokens totales=836246
- Solved global: 100.0 % (40/40)

Errores por tipo:

_(ningún item con `error`)_


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo. **Esta reconstrucción es ilustrativa, no histórica**: usa el código de `llm/prompts.py` de HOY, así que si el texto del prompt cambió después de que esta corrida se generó, lo que se ve aquí no es lo que el modelo recibió. El registro histórico real es el hash por fila (`system_prompt_hash`, ver sección 1 / `benchmarks/experiment_report.py::section_what_ran`), fijado en el momento de la corrida y nunca recalculado.

### Método `pfagent`

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

**User prompt (primer item) = request_text** — 90 caracteres; case=case14, seed=1813382119, k=1, request_id=case14-stress-000-s0

````
Load the IEEE 14-bus system and disconnect the transformer branch between bus 7 and bus 8.
````


## 3. Resultados agregados

Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`), en los 4 grupos de `metricas_pfagent_definiciones.md`: **utilidad de tarea** Form. (formulación exacta de las tool calls), V_MAE (p.u., solo sobre peticiones con formulación exacta -- toda fila con herramientas que llega al solver con la formulación correcta da exactamente cero, ver benchmarks/scoring.py) y F_MAE (MW) sobre los items con resultado, Solved (respondió correctamente de extremo a extremo); **corrección solver-grounded** Solver status (convergencia reportada = convergencia real), B_mean (residual medio de KCL de los flujos reportados, MW); **fidelidad** Faith. (por respuesta, no por número: fracción de respuestas donde todo número es trazable a una salida de tool Y viene del solve posterior al último cambio de red) y SFR (fallos declarados con seguridad); **costo** Calls (tool calls medias) y Tok. (tokens medios). Fuera de los 4 grupos, solo en este reporte (no en las tablas del paper): Claim (éxito reclamado sobre un fallo), Escalated y Wrong (silent). Escalated y Wrong (silent) junto con solved_autonomously_rate (no la columna Solved de arriba, que puede solaparse con Escalated -- una abstención de verificación puede caer sobre un item cuyo cálculo de fondo sí era correcto) suman 100 %: dónde termina cada petición -- resuelta sola, entregada a una persona, o mal contestada sin aviso; solo cuenta como Escalated una arquitectura con mecanismo de traspaso real, ver benchmarks.scoring.escalation_check) y $ (costo total USD). Porcentajes en %.

### Por método × caso

| Method | Case | N | Form. | V_MAE | F_MAE | Solved | Solver status | B_mean | Faith. | SFR | Calls | Tok. | Claim | Escalated | Wrong (silent) | $ |
|-------|------|----|----------------|-----|-----|----------------|----------------|------|----------------|----------------|-----|-----|----------|----------------|-----------------|------|
| pfagent | case14 | 40 | 100.0 (40/40) | -- | 0.00 | 100.0 (40/40) | 100.0 (40/40) | 0 | 100.0 (40/40) | 100.0 (40/40) | 4.5 | 20906 | 0.0 (0/40) | 100.0 (40/40) | 0.0 (0/40) | 0.1325 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | stress |
|-------|----------------|
| pfagent | 100.0 (40/40) |

### Solved por dificultad (%, items resueltos / items)

| Method | stress |
|-------|----------------|
| pfagent | 100.0 (40/40) |

### Verificación final (pfagent: V(x,c,z,y) aplicado a la respuesta final)

`pass_first` = pasó al primer intento; `pass_retry` = pasó tras el único reintento con el veredicto añadido; `abstained` = falló dos veces, respuesta forzada a fallo declarado sin números; `retry_mutation` = el reintento intentó una herramienta que muta la red (bloqueada, nunca ejecutada; cuenta como abstención) — ver "Integridad del reintento" abajo. N = items con `final_gate` activo (no todos los métodos lo tienen).

| Method | N | pass_first | pass_retry | abstained | retry_mutation |
|-------|----|----------|----------|----------------|-----------------|
| pfagent | 40 | 0.0 (0/40) | 0.0 (0/40) | 100.0 (40/40) | 0.0 (0/40) |


### Integridad del reintento

De 40 ítem(s) que llegaron a un reintento, 0 intentaron una herramienta que muta la red (bloqueada) en vez de corregir el reporte; se cuentan como abstención, no como "pasó". El mensaje de reintento ya no sugiere la corrección específica (p. ej. "reconnect...") y bloquea estructuralmente `modify_load`, `disconnect_line`, `reconnect_line`, `apply_remedial_action` y `load_case` mientras el reintento está en efecto.

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
request (case14-stress-000-s0, case14, difficulty=stress, seed=1813382119): Load the IEEE 14-bus system and disconnect the transformer branch between bus 7 and bus 8.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 7, "to_bus": 8})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 7, "to_bus": 8}) -> run_powerflow({})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 252.6562386075145, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
tool: disconnect_line({"from_bus": 7, "to_bus": 8})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.898954247812662, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5624 chars más]
  gate: FAIL (reasons=isolated_or_unsolved_buses, mismatch=9.78e-09 MW)
--- Ronda 2 ---
LLM: The IEEE 14-bus system has been loaded, and the transformer branch between bus 7 and bus 8 has been disconnected.

- **Total Load:** 252.66 MW
- **Total Generation:** 265.46 MW
- **Total Losses:** 12.81 MW
- **Voltage Range:** 1.01 to 1.07 p.u.

**Violations:**
- Overvoltage at buses 1, 6, 11, and 1 …[145 chars más]
--- Ronda 2 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.898954247812662, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5624 chars más]
  gate: FAIL (reasons=isolated_or_unsolved_buses, mismatch=9.78e-09 MW)
--- Ronda 3 ---
LLM: The IEEE 14-bus system has been loaded, and the transformer branch between bus 7 and bus 8 has been disconnected. However, this action has isolated bus 8, resulting in it having no valid voltage.

- **Total Load:** 252.66 MW
- **Total Generation:** 265.46 MW
- **Total Losses:** 12.81 MW
- **Voltage …[360 chars más]
--- Respuesta final ---
No numerical result is reported. Verification failed: bus 8 has no valid voltage because disconnecting the branch between bus 7 and bus 8 isolated it from the slack bus, so the network is split. Suggested next step: reconnect the branch between bus 7 and bus 8, or analyse the connected part separately. This is a declared failure of the verification step, not a claim that the network failed to converge.
--- Scoring ---
formulation=ok (exact=True); V_MAE=--; F_MAE=0.00; faithful=-- %; solved=True (declared_failure); flags=abstained; error=-; tokens=14022; cost_usd=0.0023; wall=6.0 s
````

**Ejemplo: con bandera de fallo (claimed/stale/abstained)**

````
request (case14-stress-001-s0, case14, difficulty=stress, seed=827308000): Load the 14-bus test case (case14), disconnect the line between bus 2 and bus 4, disconnect the transformer branch between bus 7 and bus 8, and finally rerun the power flow, then list every line whose loading is above 100%.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 2, "to_bus": 4}) -> disconnect_line({"from_bus": 7, "to_bus": 8}) -> run_powerflow({})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 2, "to_bus": 4}) -> disconnect_line({"from_bus": 7, "to_bus": 8}) -> run_powerflow({})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 270.1361769951196, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
tool: disconnect_line({"from_bus": 2, "to_bus": 4})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -4.717168458565059, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[5946 chars más]
  gate: PASS (reasons=-, mismatch=3.08e-08 MW)
tool: disconnect_line({"from_bus": 7, "to_bus": 8})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -4.733791919883227, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[5459 chars más]
  gate: FAIL (reasons=isolated_or_unsolved_buses, mismatch=8.78e-08 MW)
--- Ronda 2 ---
LLM: The power flow analysis has been completed after disconnecting the specified lines.

1. Summary: The power flow converged successfully after the modifications.
2. Key numbers: 
   - Total Load: 270.14 MW
   - Total Generation: 287.42 MW
   - Total Losses: 17.28 MW
   - Voltage Range: 0.9966 to 1.07 …[222 chars más]
--- Ronda 2 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000002, "va_deg": -4.733791919883227, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_p …[5459 chars más]
  gate: FAIL (reasons=isolated_or_unsolved_buses, mismatch=8.78e-08 MW)
--- Ronda 3 ---
LLM: The power flow analysis has been re-evaluated after the network modifications.

1. Summary: The power flow converged successfully, but bus 8 remains isolated with no valid voltage due to the disconnection of the line between bus 7 and bus 8.
2. Key numbers: 
   - Total Load: 270.14 MW
   - Total Gen …[391 chars más]
--- Respuesta final ---
No numerical result is reported. Verification failed: bus 8 has no valid voltage because disconnecting the branch between bus 7 and bus 8 isolated it from the slack bus, so the network is split. Suggested next step: reconnect the branch between bus 7 and bus 8, or analyse the connected part separately. This is a declared failure of the verification step, not a claim that the network failed to converge.
--- Scoring ---
formulation=ok (exact=True); V_MAE=--; F_MAE=0.00; faithful=-- %; solved=True (declared_failure); flags=abstained; error=-; tokens=21637; cost_usd=0.0034; wall=7.3 s
````

**Ejemplo: primer item**

````
request (case14-stress-002-s0, case14, difficulty=stress, seed=1627694679): Load the 14-bus test case (case14), set the active load at bus 9 to 37.7 MW, disconnect the transformer branch between bus 7 and bus 8, and finally rerun the power flow, then list every line whose loading is above 80%.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 9, "p_mw": 37.7}) -> disconnect_line({"from_bus": 7, "to_bus": 8}) -> run_powerflow({})
executed_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 9, "p_mw": 37.7}) -> disconnect_line({"from_bus": 7, "to_bus": 8}) -> run_powerflow({})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 257.9016499664761, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
--- Ronda 2 ---
tool: modify_load({"bus_id": 9, "p_mw": 37.7})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.0450000000000004, "va_deg": -5.20987075244386, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu …[6276 chars más]
  gate: PASS (reasons=-, mismatch=7.12e-09 MW)
tool: disconnect_line({"from_bus": 7, "to_bus": 8})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -5.218631984859549, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.0100000 …[5520 chars más]
  gate: FAIL (reasons=isolated_or_unsolved_buses, mismatch=1.62e-08 MW)
--- Ronda 3 ---
LLM: The power flow analysis has been completed after modifying the load and disconnecting the transformer branch.

1. **Summary**: The power flow converged successfully after the modifications.
2. **Key numbers**: 
   - Total Load: 264.43 MW
   - Total Generation: 278.62 MW
   - Total Losses: 14.19 MW …[305 chars más]
--- Ronda 3 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -5.218631984859549, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.0100000 …[5520 chars más]
  gate: FAIL (reasons=isolated_or_unsolved_buses, mismatch=1.62e-08 MW)
--- Ronda 4 ---
LLM: The power flow analysis has been re-evaluated after the network modifications, confirming the isolated state of bus 8.

1. **Summary**: The power flow converged successfully, but bus 8 remains isolated with no valid voltage.
2. **Key numbers**: 
   - Total Load: 264.43 MW
   - Total Generation: 278. …[417 chars más]
--- Respuesta final ---
No numerical result is reported. Verification failed: bus 8 has no valid voltage because disconnecting the branch between bus 7 and bus 8 isolated it from the slack bus, so the network is split. Suggested next step: reconnect the branch between bus 7 and bus 8, or analyse the connected part separately. This is a declared failure of the verification step, not a claim that the network failed to converge.
--- Scoring ---
formulation=ok (exact=True); V_MAE=--; F_MAE=0.00; faithful=-- %; solved=True (declared_failure); flags=abstained; error=-; tokens=23105; cost_usd=0.0037; wall=7.5 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- El gate verificó 142 resultados de flujo, 81 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- Ningún item terminó con `error`.
- Solved de `pfagent`: 100.0 % (40/40).
- Formulación exacta agregada sobre métodos con tools: 100.0 % (40/40).
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- De 40 items en estado de fallo, 40 lo declararon de forma segura (SFR 100.0 % (40/40)).
- 0 de 40 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 100.0 %.
- 40 items esperaban un resultado no convergido (non_converged=24, islanded=16); el método lo declaró correctamente (solved) en 100.0 % (40/40), con solved_reason `declared_failure`=40.
- Costo total 0.1325 USD; el método más caro fue `pfagent` con 0.1325 USD (100 %).
- Métodos con tools: 4.55 tool calls medias por item (máximo 7).

## 6. Archivos

Rutas absolutas bajo `results_validation_gpt-4o-mini_stress`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-4o-mini_stress/report.json   [leído: report.rescored.json]
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-4o-mini_stress/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-4o-mini_stress/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-4o-mini_stress/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-4o-mini_stress/scoreboard_per_case.json
  scoreboard.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-4o-mini_stress/scoreboard.rescored.json
  scoreboard_per_case.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-4o-mini_stress/scoreboard_per_case.rescored.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-4o-mini_stress/traces
````

