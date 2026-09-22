# Informe de experimento: `llm_only_forced_structured`

Generado el 2026-09-21 18:54 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio llm_only_forced_structured (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_nr/gpt-4o-mini/llm_only_forced_structured
````

- Reports leídos: 1 (`report.rescored.json` usado en 1; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-4o-mini`
- Métodos: `llm_only_forced:structured`
- Casos: `case14`
- Requests: generadas, N=40 por caso y seed, difficulties=todas (1 report)
- Items por dificultad: plain=10, parameterized=10, multistep=10, ambiguous=10
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-16 12:36
- Costo total: 0.0334 USD (40 items; costo medio 0.00084 USD/item)
- Items totales: 40; ok=27; con error=13; tokens totales=117129
- Solved global: 0.0 % (0/40)

Errores por tipo:

| Tipo | Items | Métodos afectados |
|---------------------|-----|--------------------------------------|
| json_parse_failed | 13 | llm_only_forced:structured (13) |


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo. **Esta reconstrucción es ilustrativa, no histórica**: usa el código de `llm/prompts.py` de HOY, así que si el texto del prompt cambió después de que esta corrida se generó, lo que se ve aquí no es lo que el modelo recibió. El registro histórico real es el hash por fila (`system_prompt_hash`, ver sección 1 / `benchmarks/experiment_report.py::section_what_ran`), fijado en el momento de la corrida y nunca recalculado.

### Método `llm_only_forced:structured`

**System prompt** (reconstrucción con el código actual, no necesariamente histórica) — 565 caracteres; strategy=structured, forced=True, sin herramientas

````
You are a power system analysis expert. You need to calculate AC power flow results based on test system data provided by the user.

Important Constraints:

- You must strictly output JSON (no extra text, no Markdown blocks).

- Do not output NaN/Infinity; all values must be finite real numbers.

- You must compute and report your best numerical estimate for every bus voltage and every branch flow. `converged` must be true and every array must be complete (one entry per bus and per branch). Do not leave arrays empty and do not state that you cannot compute.
````

**User prompt (primer item)** — 5127 caracteres; case=case14, seed=1911784258, k=1, request_id=case14-ambiguous-003-s0

````
System base: 100 MVA. Every per-unit quantity below (r_pu, x_pu, b_pu) is defined on this base. Line and transformer impedances (r_pu, x_pu, b_pu) are already in per unit on this base, not ohms per km; do not convert them further. Branch thermal ratings are not defined for this case, so branch loading is undefined: report loading_percent as 0 for every branch.

You are a power systems expert. Based on the following IEEE case14 test system data, calculate the AC power flow results.

## System Data (from pandapower network tables)

### Node Data (Bus Table: net.bus)

   name type zone  in_service
0     1    b  1.0        True
1     2    b  1.0        True
2     3    b  1.0        True
3     4    b  1.0        True
4     5    b  1.0        True
5     6    b  1.0        True
6     7    b  1.0        True
7     8    b  1.0        True
8     9    b  1.0        True
9    10    b  1.0        True
10   11    b  1.0        True
… (3 líneas omitidas de 15)

### Load Data (Load Table: net.load)

    bus       p_mw     q_mvar  in_service
0     2  21.473798  12.567615        True
1     3  85.726702  17.290948        True
2     4  45.568126  -3.717902        True
3     5   6.887322   1.449962        True
4     6  11.740497   7.861940        True
5     9  32.229269  18.135792        True
6    10   9.714580   6.260507        True
7    11   3.424253   1.761044        True
8    12   6.539657   1.715320        True
9    13  14.757610   6.340306        True
10   14  15.783969   5.296634        True

### Generator Data (Generator Table: net.gen)

   bus      p_mw  vm_pu  min_p_mw  max_p_mw  min_q_mvar  max_q_mvar  in_service
0    2  41.63323  1.045       0.0     140.0       -40.0        50.0        True
1    3   0.00000  1.010       0.0     100.0         0.0        40.0        True
2    6   0.00000  1.070       0.0     100.0        -6.0        24.0        True
3    8   0.00000  1.090       0.0     100.0        -6.0        24.0        True

### Balanced Node/External Grid (External Grid Table: net.ext_grid)

   bus  vm_pu  va_degree  in_service
0    1   1.06        0.0        True

### Line Data (Line Table: net.line)

    from_bus  to_bus     r_pu     x_pu    b_pu  parallel  in_service
0          1       2  0.01938  0.05917  0.0528         1        True
1          1       5  0.05403  0.22304  0.0492         1        True
2          2       3  0.04699  0.19797  0.0438         1        True
3          2       4  0.05811  0.17632  0.0340         1        True
4          2       5  0.05695  0.17388  0.0346         1        True
5          3       4  0.06701  0.17103  0.0128         1        True
6          4       5  0.01335  0.04211  0.0000         1        True
7          6      11  0.09498  0.19890  0.0000         1        True
8          6      12  0.12291  0.25581  0.0000         1        True
9          6      13  0.06615  0.13027  0.0000         1        True
10         9      10  0.03181  0.08450  0.0000         1        True
… (4 líneas omitidas de 16)

### Transformer Data (Transformer Table: net.trafo)

   hv_bus  lv_bus  r_pu     x_pu  shift_degree tap_side  tap_neutral  tap_min  tap_max  tap_step_percent  in_service
0       4       7   0.0  0.20912           0.0       hv          0.0      NaN      NaN               2.2        True
1       4       9   0.0  0.55618           0.0       hv          0.0      NaN      NaN               3.1        True
2       5       6   0.0  0.25202           0.0       hv          0.0      NaN      NaN               6.8        True
3       7       8   0.0  0.17615           0.0     None          NaN      NaN      NaN               NaN        True
4       7       9   0.0  0.11001           0.0     None          NaN      NaN      NaN               NaN        True

## Task
Load case14 and disconnect the line between bus ten and bus eleven.

## Output Requirements
Please calculate and return the following results (JSON format):

1) Voltage magnitude (p.u.) and phase angle (degrees) for each node

2) Active power (MW) and load factor (%) at the beginning of each branch

- For lines: `line_id` uses the row index of `net.line`

- For transformers: `line_id` uses the row index of 100000 + `net.trafo`

3) Total generation (MW), total load (MW), total losses (MW)

4) Are there any voltage overruns (<0.95 or >1.05 p.u.) or line overruns (>100%)?

Please strictly follow the following JSON schema output (all fields are complete and of correct type):

{
"converged": true/false,

"bus_voltages": [{"bus_id": 1, "vm_pu": 1.0, "va_deg": 0.0}, ...],

"line_flows": [{"line_id": 0, "p_from_mw": 0.0, "loading_percent": 0.0}, ...],

"total_generation_mw": 0.0,

"total_load_mw": 0.0,
  "total_loss_mw": 0.0
}

[Important] bus_id must use the `name` column of net.bus (the usual IEEE/MATPOWER 1..N numbering), not the row index of net.bus.
````


## 3. Resultados agregados

Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`), en los 4 grupos de `metricas_pfagent_definiciones.md`: **utilidad de tarea** Form. (formulación exacta de las tool calls), V_MAE (p.u., solo sobre peticiones con formulación exacta -- toda fila con herramientas que llega al solver con la formulación correcta da exactamente cero, ver benchmarks/scoring.py) y F_MAE (MW) sobre los items con resultado, Solved (respondió correctamente de extremo a extremo); **corrección solver-grounded** Solver status (convergencia reportada = convergencia real), B_mean (residual medio de KCL de los flujos reportados, MW); **fidelidad** Faith. (por respuesta, no por número: fracción de respuestas donde todo número es trazable a una salida de tool Y viene del solve posterior al último cambio de red) y SFR (fallos declarados con seguridad); **costo** Calls (tool calls medias) y Tok. (tokens medios). Fuera de los 4 grupos, solo en este reporte (no en las tablas del paper): Claim (éxito reclamado sobre un fallo), Escalated y Wrong (silent). Escalated y Wrong (silent) junto con solved_autonomously_rate (no la columna Solved de arriba, que puede solaparse con Escalated -- una abstención de verificación puede caer sobre un item cuyo cálculo de fondo sí era correcto) suman 100 %: dónde termina cada petición -- resuelta sola, entregada a una persona, o mal contestada sin aviso; solo cuenta como Escalated una arquitectura con mecanismo de traspaso real, ver benchmarks.scoring.escalation_check) y $ (costo total USD). Porcentajes en %.

### Por método × caso

| Method | Case | N | Form. | V_MAE solved | V_MAE all | B_mean solved | B_mean all | Solved | Escalated | Wrong-unflagged | Traceable | Tokens | Time (s) | Claim | Escalated | Wrong (silent) | $ |
|--------------------------------|------|----|-----|---------------|---------|----------------|----------|----------|----------|------------------|---------|------|--------|-----|----------|-----------------|------|
| llm_only_forced:structured | case14 | 40 | -- | 2.74e-02 | 2.74e-02 | 1.20e+01 | 1.20e+01 | 0.0 (0/40) | 0.0 (0/40) | 100.0 | 0.0 | 2928 | 13.96 | -- | 0.0 (0/40) | 100.0 (40/40) | 0.0334 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|--------------------------------|-----|----------------|---------|---------|
| llm_only_forced:structured | n/a | n/a | n/a | n/a |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|--------------------------------|----------|----------------|----------|----------|
| llm_only_forced:structured | 0.0 (0/10) | 0.0 (0/10) | 0.0 (0/10) | 0.0 (0/10) |

### Tipos de error de formulación (conteo de items)

| Method | unparsed |
|--------------------------------|--------|
| llm_only_forced:structured | 13 |

### Errores de ejecución por método (conteo de items con `error`)

| Method | json_parse_failed |
|--------------------------------|---------------------|
| llm_only_forced:structured | 13 |


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `llm_only_forced:structured`

**Ejemplo: no resuelto**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
{
  "converged": true,
  "bus_voltages": [
    {"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0},
    {"bus_id": 2, "vm_pu": 1.045, "va_deg": -2.0},
    {"bus_id": 3, "vm_pu": 1.01, "va_deg": -5.0},
    {"bus_id": 4, "vm_pu": 1.0, "va_deg": -7.0},
    {"bus_id": 5, "vm_pu": 1.0, "va_deg": -8.0},
    {"bus_id": 6, "vm_pu": 1.07, "va_deg": -10.0},
    {"bus_id": 7, "vm_pu": 1.0, "va_deg": -12.0},
    {"bus_id": 8, "vm_pu": 1.09, "va_deg": -15.0},
    {"bus_id": 9, "vm_pu": 1.0, "va_deg": -20.0},
    {"bus_id": 10, "vm_pu": 1.0, "va_deg": -25.0},
    {"bus_id": 11, "vm_pu": 1.0, "va_deg": -30.0},
    {"bus_id": 12, "vm_pu": 1.0, "va_deg": -35.0},
    {"bus_id": 13, "vm_pu": 1.0, "va_deg": -40.0},
    {"bus_id": 14, "vm_pu": 1.0, "va_deg": -45.0}
  ],
  "line_flows": [
    {"line_id": 0, "p_from_mw" …[997 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=2.67e-02; F_MAE=35.45; faithful=0.0 %; solved=False (voltage_error); flags=-; error=-; tokens=2895; cost_usd=0.0008; wall=15.1 s
````

**Ejemplo: primer item**

````
request (case14-ambiguous-007-s0, case14, difficulty=ambiguous, seed=2073320062): Load the 14-bus test case (case14) and disconnect the line between bus 6 and bus 13 (1-based).
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 6, "to_bus": 13})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
{
  "converged": true,
  "bus_voltages": [
    {"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0},
    {"bus_id": 2, "vm_pu": 1.045, "va_deg": -2.5},
    {"bus_id": 3, "vm_pu": 1.01, "va_deg": -5.0},
    {"bus_id": 4, "vm_pu": 1.0, "va_deg": -7.5},
    {"bus_id": 5, "vm_pu": 1.0, "va_deg": -10.0},
    {"bus_id": 6, "vm_pu": 1.07, "va_deg": -12.0},
    {"bus_id": 7, "vm_pu": 1.0, "va_deg": -15.0},
    {"bus_id": 8, "vm_pu": 1.09, "va_deg": -17.0},
    {"bus_id": 9, "vm_pu": 1.0, "va_deg": -20.0},
    {"bus_id": 10, "vm_pu": 1.0, "va_deg": -22.0},
    {"bus_id": 11, "vm_pu": 1.0, "va_deg": -25.0},
    {"bus_id": 12, "vm_pu": 1.0, "va_deg": -27.0},
    {"bus_id": 13, "vm_pu": 1.0, "va_deg": -30.0},
    {"bus_id": 14, "vm_pu": 1.0, "va_deg": -32.0}
  ],
  "line_flows": [
    {"line_id": 0, "p_from_mw …[994 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=2.00e-02; F_MAE=37.93; faithful=14.8 %; solved=False (voltage_error); flags=-; error=-; tokens=2908; cost_usd=0.0008; wall=15.3 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- LLM-only: V_MAE entre 2.74e-02 (llm_only_forced:structured/case14) y 2.74e-02 (llm_only_forced:structured/case14) p.u. sobre los items que devolvieron números.
- 0.0 % (0/40) de abstención en LLM-only (respuesta con `converged=false` o arrays vacíos).
- En LLM-only, 0 items no resueltos por `convergence_mismatch` y 27 por `voltage_error`.
- 13 items con `json_parse_failed`: la respuesta LLM-only no fue JSON parseable.
- Solved de `llm_only_forced:structured`: 0.0 % (0/40).
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- Trazabilidad de números (Faith.) media en LLM-only: 7.7 % (sin tools, todo número es no trazable salvo los copiados de la request).
- Costo total 0.0334 USD; el método más caro fue `llm_only_forced:structured` con 0.0334 USD (100 %).

## 6. Archivos

Rutas absolutas bajo `llm_only_forced_structured`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_nr/gpt-4o-mini/llm_only_forced_structured/report.json   [leído: report.rescored.json]
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_nr/gpt-4o-mini/llm_only_forced_structured/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_nr/gpt-4o-mini/llm_only_forced_structured/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_nr/gpt-4o-mini/llm_only_forced_structured/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_nr/gpt-4o-mini/llm_only_forced_structured/scoreboard_per_case.json
  scoreboard.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_nr/gpt-4o-mini/llm_only_forced_structured/scoreboard.rescored.json
  scoreboard_per_case.rescored.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_nr/gpt-4o-mini/llm_only_forced_structured/scoreboard_per_case.rescored.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_nr/gpt-4o-mini/llm_only_forced_structured/traces
````

