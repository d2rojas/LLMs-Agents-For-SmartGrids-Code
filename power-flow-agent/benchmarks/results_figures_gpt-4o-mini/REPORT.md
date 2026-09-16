# Informe de experimento: `results_figures_gpt-4o-mini`

Generado el 2026-09-16 08:20 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio results_figures_gpt-4o-mini (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_figures_gpt-4o-mini
````

- Reports leídos: 1 (`report.rescored.json` usado en 0; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-4o-mini`
- Métodos: `pfagent`
- Casos: `case14`
- Requests: archivo `/private/tmp/claude-501/-Users-lzanda-Documents-REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/407316ee-3d85-41c5-8036-570b8b373279/scratchpad/figure_pair_case14.jsonl` (1 report)
- Items por dificultad: multistep=1, stress=1
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-16 08:19
- Costo total: 0.0165 USD (2 items; costo medio 0.00826 USD/item)
- Items totales: 2; ok=2; con error=0; tokens totales=107537
- Solved global: 50.0 % (1/2)

Errores por tipo:

_(ningún item con `error`)_


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo.

### Método `pfagent`

**System prompt (SYSTEM_PROMPT_EN)** — 1375 caracteres; architecture=react, gate=False, memory=True

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
- Bus and line identifiers in the request are MATPOWER 1-based ids; pass them to the tools as given.
- After a network modification, re-solve before reporting any value.
- Always reply in English.

## Reply format
After each analysis, reply in this structure:
1. One-sentence summary
2. Key numbers (total load, total generation, total losses, voltage range) taken from the tool outputs
3. Violations, if any
4. Suggested next step
````

**User prompt (primer item) = request_text** — 242 caracteres; case=case14, seed=1083806780, k=1, request_id=case14-multistep-022-s0

````
Load case14, disconnect the line between bus 9 and bus 10, set the active load at bus 3 to 118.6 MW, set the active load at bus 4 to 53.6 MW, and finally run an N-1 contingency analysis ranked by max violations and report the 8 worst outages.
````


## 3. Resultados agregados

Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`), en los 4 grupos de `metricas_pfagent_definiciones.md`: **utilidad de tarea** Form. (formulación exacta de las tool calls), V_MAE (p.u.) y F_MAE (MW) sobre los items con resultado, Solved (respondió correctamente de extremo a extremo); **corrección solver-grounded** Solver status (convergencia reportada = convergencia real), B_mean (residual medio de KCL de los flujos reportados, MW); **fidelidad** Faith. (números de la respuesta trazables a salidas de tools) y SFR (fallos declarados con seguridad); **costo** Calls (tool calls medias) y Tok. (tokens medios). Fuera de los 4 grupos, solo en este reporte (no en las tablas del paper): Claim (éxito reclamado sobre un fallo), Abst. (abstención en items resolubles) y $ (costo total USD). Porcentajes en %.

### Por método × caso

| Method | Case | N | Form. | V_MAE | F_MAE | Solved | Solver status | B_mean | Faith. | SFR | Calls | Tok. | Claim | Abst. | $ |
|-------|------|----|----------|-----|-----|----------|----------------|------|------|-------------|-----|-----|---------|----------|------|
| pfagent | case14 | 2 | 50.0 (1/2) | -- | 0.00 | 50.0 (1/2) | 100.0 (2/2) | 0 | 100.0 | 100.0 (1/1) | 5.0 | 53768 | 0.0 (0/1) | 50.0 (1/2) | 0.0165 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | multistep | stress |
|-------|---------|-------------|
| pfagent | 0.0 (0/1) | 100.0 (1/1) |

### Solved por dificultad (%, items resueltos / items)

| Method | multistep | stress |
|-------|---------|-------------|
| pfagent | 0.0 (0/1) | 100.0 (1/1) |

### Verificación final (pfagent: V(x,c,z,y) aplicado a la respuesta final)

`pass_first` = pasó al primer intento; `pass_retry` = pasó tras el único reintento con el veredicto añadido; `abstained` = falló dos veces, respuesta forzada a fallo declarado sin números. N = items con `final_gate` activo (no todos los métodos lo tienen).

| Method | N | pass_first | pass_retry | abstained |
|-------|----|----------|----------|----------|
| pfagent | 2 | 0.0 (0/2) | 50.0 (1/2) | 50.0 (1/2) |

### Tipos de error de formulación (conteo de items)

| Method | extra_step | ok |
|-------|----------|----|
| pfagent | 1 | 1 |

### Errores de ejecución por método (conteo de items con `error`)

_(ningún item con `error`)_


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `pfagent`

**Ejemplo: resuelto (solved=True)**

````
request (case14-stress-006-s0, case14, difficulty=stress, seed=556019486): Load case14 and disconnect the transformer branch between bus 7 and bus 8.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 7, "to_bus": 8})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 7, "to_bus": 8}) -> run_powerflow({})
fuente de la traza: archivo de traza completo
--- Ronda 1 ---
tool: load_case({"case_name": "case14"})
  output: {"case_name": "case14", "n_buses": 14, "n_generators": 5, "n_lines": 20, "n_loads": 11, "total_load_mw": 251.83093927460206, "total_gen_capacity_mw": 772.4000000000001}
  gate: n/a (no es un resultado de flujo)
tool: disconnect_line({"from_bus": 7, "to_bus": 8})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.763768374971019, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5505 chars más]
  gate: FAIL (reasons=isolated_or_unsolved_buses, mismatch=1.1e-08 MW)
--- Ronda 2 ---
LLM: The IEEE 14-bus system has been loaded, and the transformer branch between bus 7 and bus 8 has been successfully disconnected.

- **Key numbers**: Total load: 251.83 MW, Total generation: 264.25 MW, Total losses: 12.42 MW, Voltage range: 1.01 to 1.07 p.u.
- **Violations**: There are overvoltage viol …[166 chars más]
--- Ronda 2 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.763768374971019, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.01, "va …[5505 chars más]
  gate: FAIL (reasons=isolated_or_unsolved_buses, mismatch=1.1e-08 MW)
--- Ronda 3 ---
LLM: The IEEE 14-bus system has been loaded, and the transformer branch between bus 7 and bus 8 has been successfully disconnected. However, bus 8 remains isolated and has no valid voltage.

- **Key numbers**: Total load: 251.83 MW, Total generation: 264.25 MW, Total losses: 12.42 MW, Voltage range: 1.01 …[307 chars más]
--- Respuesta final ---
The final answer could not be verified after one retry, so no numerical result is reported. Verification failed on: no_isolated_buses. This is a declared failure of the verification step, not a claim that the network failed to converge.
--- Scoring ---
formulation=ok (exact=True); V_MAE=--; F_MAE=0.00; faithful=-- %; solved=True (declared_failure); flags=abstained,abstained_on_solvable; error=-; tokens=13608; cost_usd=0.0022; wall=6.5 s
````

**Ejemplo: formulación fallida (formulation_exact=False)**

````
request (case14-multistep-022-s0, case14, difficulty=multistep, seed=1083806780): Load case14, disconnect the line between bus 9 and bus 10, set the active load at bus 3 to 118.6 MW, set the active load at bus 4 to 53.6 MW, and finally run an N-1 contingency analysis ranked by max violations and report the 8 worst outages.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 9, "to_bus": 10}) -> modify_load({"bus_id": 3, "p_mw": 118.6}) -> modify_load({"bus_id": 4, "p_mw": 53.6}) -> run_n1_contingency({"top_k": 8, "criteria": "max_violations"})
executed_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 9, "to_bus": 10}) -> modify_load({"bus_id": 3, "p_mw": 118.6}) -> modify_load({"bus_id": 4, "p_mw": 53.6}) -> run_n1_contingency({"top_k": 8, "criteria": "max_violations"}) -> run_powerflow({}) -> run_n1_contingency({"top_k": 8, "criteria": "max_violations"})
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

1. **Summary**: The N-1 contingency analysis identified the worst outages, with significant voltage violations observed.
2. **Key Numbers**: 
   - Total Load: 264.09 MW
   - Total Generation: 278.14 MW
   - …[379 chars más]
--- Ronda 4 ---
tool: run_powerflow({})
  output: {"case_name": "case14", "converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0, "is_violation": true, "violation_type": "overvoltage"}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -5.672176280633835, "is_violation": false, "violation_type": null}, {"bus_id": 3, "vm_pu": 1.0100000 …[6073 chars más]
  gate: PASS (reasons=-, mismatch=7.73e-09 MW)
--- Ronda 5 ---
tool: run_n1_contingency({"top_k": 8, "criteria": "max_violations"})
  output: {"plot_type": "n1_ranking", "figure_json": "{\"data\":[{\"cliponaxis\":false,\"hoverinfo\":\"text\",\"hovertext\":[\"\\u003cb\\u003eOutage\\u003c\\u002fb\\u003e: 10-11 (line)\\u003cbr\\u003e\\u003cb\\u003eConverged\\u003c\\u002fb\\u003e: True\\u003cbr\\u003e\\u003cb\\u003eVoltage violations\\u003c\\ …[19612 chars más]
  gate: n/a (no es un resultado de flujo)
--- Ronda 6 ---
LLM: The analysis of the IEEE 14-bus system after the specified modifications has been completed again, ensuring all values are current.

1. **Summary**: The N-1 contingency analysis identified the worst outages, with significant voltage violations observed.
2. **Key Numbers**: 
   - Total Load: 286.75 M …[394 chars más]
--- Respuesta final ---
The analysis of the IEEE 14-bus system after the specified modifications has been completed again, ensuring all values are current.

1. **Summary**: The N-1 contingency analysis identified the worst outages, with significant voltage violations observed.
2. **Key Numbers**: 
   - Total Load: 286.75 MW
   - Total Generation: 304.21 MW
   - Total Losses: 17.46 MW
   - Voltage Range: 1.0100 to 1.0900 pu
3. **Violations**: There are multiple voltage violations at several buses, particularly with bus 1, which has 8 violations.
4. **Suggested Next Step**: Consider implementing remedial actions to address the voltage violations and improve system stability. Would you like to proceed with that?
--- Scoring ---
formulation=extra_step (exact=False); V_MAE=0; F_MAE=0.00; faithful=100.0 %; solved=False (formulation); flags=-; error=-; tokens=93929; cost_usd=0.0143; wall=14.3 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- El gate verificó 6 resultados de flujo, 2 fallaron la verificación y se activó (retuvo números) 0 veces en 0 items.
- Ningún item terminó con `error`.
- Solved de `pfagent`: 50.0 % (1/2).
- Formulación exacta agregada sobre métodos con tools: 50.0 % (1/2).
- Formulación por dificultad: mejor `stress` 100.0 % (1/1), peor `multistep` 0.0 % (0/1).
- Errores de formulación más frecuentes: `extra_step`=1.
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- De 1 items en estado de fallo, 1 lo declararon de forma segura (SFR 100.0 % (1/1)).
- 0 de 2 items con mutación de red reportaron estado obsoleto (stale_state).
- Trazabilidad de números (Faith.) media con tools: 100.0 %.
- 1 items esperaban un resultado no convergido (islanded=1); el método lo declaró correctamente (solved) en 100.0 % (1/1), con solved_reason `declared_failure`=1.
- Costo total 0.0165 USD; el método más caro fue `pfagent` con 0.0165 USD (100 %).
- Métodos con tools: 5.00 tool calls medias por item (máximo 7).

## 6. Archivos

Rutas absolutas bajo `results_figures_gpt-4o-mini`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_figures_gpt-4o-mini/report.json
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_figures_gpt-4o-mini/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_figures_gpt-4o-mini/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_figures_gpt-4o-mini/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_figures_gpt-4o-mini/scoreboard_per_case.json
  traces (2 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_figures_gpt-4o-mini/traces
````

