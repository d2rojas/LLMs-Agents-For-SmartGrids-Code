# Informe de experimento: `results_validation_gpt-5.4_llm_only`

Generado el 2026-09-15 22:42 por benchmarks/experiment_report.py a partir de 1 report(s) del directorio results_validation_gpt-5.4_llm_only (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_llm_only
````

- Reports leídos: 1 (`report.rescored.json` usado en 0; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-5.4`
- Métodos: `llm_only_forced:cot`, `llm_only_forced:structured`
- Casos: `case14`, `case30`
- Requests: generadas, N=5 por caso y seed, difficulties=todas (1 report)
- Items por dificultad: plain=8, parameterized=4, multistep=4, ambiguous=4
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-15 22:41
- Costo total: 0.5703 USD (20 items; costo medio 0.02851 USD/item)
- Items totales: 20; ok=19; con error=1; tokens totales=89121
- Solved global: 20.0 % (4/20)

Errores por tipo:

| Tipo | Items | Métodos afectados |
|---------------------|-----|-------------------------------------|
| json_parse_failed | 1 | llm_only_forced:structured (1) |


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo.

### Método `llm_only_forced:cot`

**System prompt** — 860 caracteres; strategy=cot, forced=True, sin herramientas

````
You are a power system analysis expert. You need to calculate AC power flow results based on test system data provided by the user.

Important Constraints:

- You must strictly output JSON (no extra text, no Markdown blocks).

- Do not output NaN/Infinity; all values must be finite real numbers.

- You must compute and report your best numerical estimate for every bus voltage and every branch flow. `converged` must be true and every array must be complete (one entry per bus and per branch). Do not leave arrays empty and do not state that you cannot compute.

Reasoning mode: you MAY write a short step-by-step reasoning in plain text before the answer. The final JSON object must be the LAST thing in the response, inside a single ```json fenced block, and it must be the only JSON object in the response. Do not use curly braces in the reasoning text.
````

**User prompt (primer item)** — 6326 caracteres; case=case14, seed=1911784258, k=1, request_id=case14-ambiguous-003-s0

````
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
0     1  21.473798  12.567615        True
1     2  85.726702  17.290948        True
2     3  45.568126  -3.717902        True
3     4   6.887322   1.449962        True
4     5  11.740497   7.861940        True
5     8  32.229269  18.135792        True
6     9   9.714580   6.260507        True
7    10   3.424253   1.761044        True
8    11   6.539657   1.715320        True
9    12  14.757610   6.340306        True
10   13  15.783969   5.296634        True

### Generator Data (Generator Table: net.gen)

   bus      p_mw  vm_pu  min_p_mw  max_p_mw  min_q_mvar  max_q_mvar  in_service
0    1  41.63323  1.045       0.0     140.0       -40.0        50.0        True
1    2   0.00000  1.010       0.0     100.0         0.0        40.0        True
2    5   0.00000  1.070       0.0     100.0        -6.0        24.0        True
3    7   0.00000  1.090       0.0     100.0        -6.0        24.0        True

### Balanced Node/External Grid (External Grid Table: net.ext_grid)

   bus  vm_pu  va_degree  in_service
0    0   1.06        0.0        True

### Line Data (Line Table: net.line)

    from_bus  to_bus  length_km  r_ohm_per_km  x_ohm_per_km  c_nf_per_km      max_i_ka   df  parallel  in_service
0          0       1        1.0      3.532005     10.783732   768.484773     42.339020  1.0         1        True
1          0       4        1.0      9.846967     40.649040   716.088084     42.339020  1.0         1        True
2          1       2        1.0      8.563928     36.080033   637.493051     42.339020  1.0         1        True
3          1       3        1.0     10.590547     32.134320   494.857619     42.339020  1.0         1        True
4          1       4        1.0     10.379138     31.689630   503.590401     42.339020  1.0         1        True
5          2       3        1.0     12.212573     31.170217   186.299339     42.339020  1.0         1        True
6          3       4        1.0      2.433038      7.674548     0.000000     42.339020  1.0         1        True
7          5      10        1.0      0.000041      0.000086     0.000000  27479.652235  1.0         1        True
8          5      11        1.0      0.000053      0.000111     0.000000  27479.652235  1.0         1        True
9          5      12        1.0      0.000029      0.000056     0.000000  27479.652235  1.0         1        True
10         8       9        1.0      0.000014      0.000037     0.000000  27479.652235  1.0         1        True
… (4 líneas omitidas de 16)

### Transformer Data (Transformer Table: net.trafo)

   hv_bus  lv_bus  sn_mva  vn_hv_kv  vn_lv_kv  vk_percent  vkr_percent  pfe_kw  i0_percent  shift_degree tap_side  tap_neutral  tap_min  tap_max  tap_step_percent  in_service
0       3       6  9900.0     135.0    14.000    2070.288          0.0     0.0         0.0           0.0       hv          0.0      NaN      NaN               2.2        True
1       3       8  9900.0     135.0     0.208    5506.182          0.0     0.0         0.0           0.0       hv          0.0      NaN      NaN               3.1        True
2       4       5  9900.0     135.0     0.208    2494.998          0.0     0.0         0.0           0.0       hv          0.0      NaN      NaN               6.8        True
3       6       7  9900.0      14.0    12.000    1743.885          0.0     0.0         0.0           0.0     None          NaN      NaN      NaN               NaN        True
4       6       8  9900.0      14.0     0.208    1089.099          0.0     0.0         0.0           0.0     None          NaN      NaN      NaN               NaN        True

## Task
Load case14 and disconnect the line between bus ten and bus eleven.

## Reasoning Instructions
Before producing the final JSON, reason step by step:
1. Which buses does the request refer to (display ids, slack bus, load and generator buses)?
2. Which lines/branches are involved (from_bus-to_bus, line_id convention)?
3. Which quantities and units are asked for (MW, Mvar, p.u., degrees, % loading)?
4. What changes with respect to the base case, and which power balance must hold?
Write the reasoning first, then the final JSON as the last part of the response.

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

### Método `llm_only_forced:structured`

**System prompt** — 565 caracteres; strategy=structured, forced=True, sin herramientas

````
You are a power system analysis expert. You need to calculate AC power flow results based on test system data provided by the user.

Important Constraints:

- You must strictly output JSON (no extra text, no Markdown blocks).

- Do not output NaN/Infinity; all values must be finite real numbers.

- You must compute and report your best numerical estimate for every bus voltage and every branch flow. `converged` must be true and every array must be complete (one entry per bus and per branch). Do not leave arrays empty and do not state that you cannot compute.
````

**User prompt (primer item)** — 5831 caracteres; case=case14, seed=1911784258, k=1, request_id=case14-ambiguous-003-s0

````
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
0     1  21.473798  12.567615        True
1     2  85.726702  17.290948        True
2     3  45.568126  -3.717902        True
3     4   6.887322   1.449962        True
4     5  11.740497   7.861940        True
5     8  32.229269  18.135792        True
6     9   9.714580   6.260507        True
7    10   3.424253   1.761044        True
8    11   6.539657   1.715320        True
9    12  14.757610   6.340306        True
10   13  15.783969   5.296634        True

### Generator Data (Generator Table: net.gen)

   bus      p_mw  vm_pu  min_p_mw  max_p_mw  min_q_mvar  max_q_mvar  in_service
0    1  41.63323  1.045       0.0     140.0       -40.0        50.0        True
1    2   0.00000  1.010       0.0     100.0         0.0        40.0        True
2    5   0.00000  1.070       0.0     100.0        -6.0        24.0        True
3    7   0.00000  1.090       0.0     100.0        -6.0        24.0        True

### Balanced Node/External Grid (External Grid Table: net.ext_grid)

   bus  vm_pu  va_degree  in_service
0    0   1.06        0.0        True

### Line Data (Line Table: net.line)

    from_bus  to_bus  length_km  r_ohm_per_km  x_ohm_per_km  c_nf_per_km      max_i_ka   df  parallel  in_service
0          0       1        1.0      3.532005     10.783732   768.484773     42.339020  1.0         1        True
1          0       4        1.0      9.846967     40.649040   716.088084     42.339020  1.0         1        True
2          1       2        1.0      8.563928     36.080033   637.493051     42.339020  1.0         1        True
3          1       3        1.0     10.590547     32.134320   494.857619     42.339020  1.0         1        True
4          1       4        1.0     10.379138     31.689630   503.590401     42.339020  1.0         1        True
5          2       3        1.0     12.212573     31.170217   186.299339     42.339020  1.0         1        True
6          3       4        1.0      2.433038      7.674548     0.000000     42.339020  1.0         1        True
7          5      10        1.0      0.000041      0.000086     0.000000  27479.652235  1.0         1        True
8          5      11        1.0      0.000053      0.000111     0.000000  27479.652235  1.0         1        True
9          5      12        1.0      0.000029      0.000056     0.000000  27479.652235  1.0         1        True
10         8       9        1.0      0.000014      0.000037     0.000000  27479.652235  1.0         1        True
… (4 líneas omitidas de 16)

### Transformer Data (Transformer Table: net.trafo)

   hv_bus  lv_bus  sn_mva  vn_hv_kv  vn_lv_kv  vk_percent  vkr_percent  pfe_kw  i0_percent  shift_degree tap_side  tap_neutral  tap_min  tap_max  tap_step_percent  in_service
0       3       6  9900.0     135.0    14.000    2070.288          0.0     0.0         0.0           0.0       hv          0.0      NaN      NaN               2.2        True
1       3       8  9900.0     135.0     0.208    5506.182          0.0     0.0         0.0           0.0       hv          0.0      NaN      NaN               3.1        True
2       4       5  9900.0     135.0     0.208    2494.998          0.0     0.0         0.0           0.0       hv          0.0      NaN      NaN               6.8        True
3       6       7  9900.0      14.0    12.000    1743.885          0.0     0.0         0.0           0.0     None          NaN      NaN      NaN               NaN        True
4       6       8  9900.0      14.0     0.208    1089.099          0.0     0.0         0.0           0.0     None          NaN      NaN      NaN               NaN        True

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

Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`): Solved = respondió correctamente de extremo a extremo; Form. = formulación exacta de las tool calls; V_MAE (p.u.) y F_MAE (MW) sobre los items con resultado; FR = tasa de convergencia/feasibility; Faith. = números de la respuesta trazables a salidas de tools; SFR = fallos declarados con seguridad; Claim = éxito reclamado sobre un fallo; Abst. = abstención en items resolubles; Calls = tool calls medias; Tok. = tokens medios; TTV = tiempo medio (s); $ = costo total USD. Porcentajes en %.

### Por método × caso

| Method | Case | N | Form. | V_MAE | F_MAE | Solved | Solver status | B_mean | Faith. | SFR | Calls | Tok. | $ |
|--------------------------------|------|----|-----|--------|-----|------|----------------|------|------|----|-----|----|------|
| llm_only_forced:cot | case14 | 5 | -- | 2.17e-02 | 4.71 | 40.0 | 100.0 | -- | 0.3 | -- | n/a | 3696 | 0.1183 |
| llm_only_forced:cot | case30 | 5 | -- | 1.39e-02 | 9.16 | 0.0 | 100.0 | -- | 4.4 | -- | n/a | 5807 | 0.2001 |
| llm_only_forced:structured | case14 | 5 | -- | 5.99e-03 | 4.58 | 40.0 | 100.0 | -- | 0.3 | -- | n/a | 3186 | 0.0911 |
| llm_only_forced:structured | case30 | 5 | -- | 1.44e-02 | 8.64 | 0.0 | 100.0 | -- | 3.3 | -- | n/a | 5135 | 0.1607 |

### Agregado por método (media ponderada por items sobre todos los casos)

| Method | Case | N | Form. | V_MAE | F_MAE | Solved | Solver status | B_mean | Faith. | SFR | Calls | Tok. | $ |
|--------------------------------|-------|----|-----|--------|-----|------|----------------|------|------|----|-----|----|------|
| llm_only_forced:cot | 2 casos | 10 | -- | 1.78e-02 | 6.94 | 20.0 | 100.0 | -- | 2.3 | -- | n/a | 4751 | 0.3184 |
| llm_only_forced:structured | 2 casos | 10 | -- | 9.74e-03 | 6.39 | 20.0 | 100.0 | -- | 1.8 | -- | n/a | 4161 | 0.2518 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|--------------------------------|-----|----------------|---------|---------|
| llm_only_forced:cot | n/a | n/a | n/a | n/a |
| llm_only_forced:structured | n/a | n/a | n/a | n/a |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|--------------------------------|----------|----------------|---------|---------|
| llm_only_forced:cot | 25.0 (1/4) | 50.0 (1/2) | 0.0 (0/2) | 0.0 (0/2) |
| llm_only_forced:structured | 25.0 (1/4) | 50.0 (1/2) | 0.0 (0/2) | 0.0 (0/2) |

### Tipos de error de formulación (conteo de items)

| Method | unparsed |
|--------------------------------|--------|
| llm_only_forced:structured | 1 |

### Errores de ejecución por método (conteo de items con `error`)

| Method | json_parse_failed |
|--------------------------------|---------------------|
| llm_only_forced:structured | 1 |


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `llm_only_forced:cot`

**Ejemplo: resuelto (solved=True)**

````
request (case14-parameterized-001-s0, case14, difficulty=parameterized, seed=827308000): Load the IEEE 14-bus system and run an N-1 contingency analysis ranked by min voltage and report the 3 worst outages.
intended_calls: load_case({"case_name": "case14"}) -> run_n1_contingency({"top_k": 3, "criteria": "min_voltage"})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
```json
{
  "converged": true,
  "bus_voltages": [
    {"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0},
    {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.98},
    {"bus_id": 3, "vm_pu": 1.01, "va_deg": -12.72},
    {"bus_id": 4, "vm_pu": 1.017, "va_deg": -10.33},
    {"bus_id": 5, "vm_pu": 1.02, "va_deg": -8.78},
    {"bus_id": 6, "vm_pu": 1.07, "va_deg": -14.22},
    {"bus_id": 7, "vm_pu": 1.062, "va_deg": -13.37},
    {"bus_id": 8, "vm_pu": 1.09, "va_deg": -13.36},
    {"bus_id": 9, "vm_pu": 1.056, "va_deg": -14.94},
    {"bus_id": 10, "vm_pu": 1.051, "va_deg": -15.1},
    {"bus_id": 11, "vm_pu": 1.057, "va_deg": -14.79},
    {"bus_id": 12, "vm_pu": 1.055, "va_deg": -15.08},
    {"bus_id": 13, "vm_pu": 1.05, "va_deg": -15.16},
    {"bus_id": 14, "vm_pu": 1.036, "va_deg": -16.04}
  ],
  "line_fl …[1405 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=4.92e-04; F_MAE=2.78; faithful=0.0 %; solved=True (numeric_ok); flags=-; error=-; tokens=3561; cost_usd=0.0216; wall=8.1 s
````

**Ejemplo: no resuelto**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
Bus ids by name are 1 to 14. Slack bus is display bus 1 and corresponds to ext_grid at row-index bus 0. PV generator buses are display buses 2, 3, 6, 8 corresponding to row-index buses 1, 2, 5, 7. Load buses are display buses 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14 from the load table row-index mapping plus the pure PQ buses without generation control.

The branch ids for lines use net.line row index 0 to 14. The requested outage is the line between bus ten and bus eleven in display numbering, which corresponds to display buses 10 and 11. In the provided net.line table there is no direct 10 to 11 line; the closest relevant line is row 12 connecting row-index buses 9 to 10, which are display buses 10 to 11. So line_id 12 is disconnected. Transformer ids use 100000 plus trafo row index, so 1000 …[3154 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=7.85e-02; F_MAE=2.33; faithful=0.0 %; solved=False (voltage_error); flags=-; error=-; tokens=3967; cost_usd=0.0279; wall=26.4 s
````

**Ejemplo: primer item**

````
request (case14-multistep-002-s0, case14, difficulty=multistep, seed=1627694679): Load the 14-bus test case (case14), disconnect the line between bus 6 and bus 13, disconnect the line between bus 12 and bus 13, and finally rerun the power flow, then list every line whose loading is above 100%.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 6, "to_bus": 13}) -> disconnect_line({"from_bus": 12, "to_bus": 13}) -> run_powerflow({})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
```json
{
  "converged": true,
  "bus_voltages": [
    {"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0},
    {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.98},
    {"bus_id": 3, "vm_pu": 1.01, "va_deg": -12.72},
    {"bus_id": 4, "vm_pu": 1.017, "va_deg": -10.33},
    {"bus_id": 5, "vm_pu": 1.019, "va_deg": -8.78},
    {"bus_id": 6, "vm_pu": 1.07, "va_deg": -14.22},
    {"bus_id": 7, "vm_pu": 1.061, "va_deg": -13.37},
    {"bus_id": 8, "vm_pu": 1.09, "va_deg": -13.36},
    {"bus_id": 9, "vm_pu": 1.056, "va_deg": -14.94},
    {"bus_id": 10, "vm_pu": 1.051, "va_deg": -15.1},
    {"bus_id": 11, "vm_pu": 1.057, "va_deg": -14.79},
    {"bus_id": 12, "vm_pu": 1.055, "va_deg": -15.08},
    {"bus_id": 13, "vm_pu": 1.05, "va_deg": -15.16},
    {"bus_id": 14, "vm_pu": 1.036, "va_deg": -16.04}
  ],
  "line_f …[1422 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=2.00e-02; F_MAE=8.23; faithful=1.4 %; solved=False (voltage_error); flags=-; error=-; tokens=3586; cost_usd=0.0217; wall=8.1 s
````

### Método `llm_only_forced:structured`

**Ejemplo: resuelto (solved=True)**

````
request (case14-parameterized-001-s0, case14, difficulty=parameterized, seed=827308000): Load the IEEE 14-bus system and run an N-1 contingency analysis ranked by min voltage and report the 3 worst outages.
intended_calls: load_case({"case_name": "case14"}) -> run_n1_contingency({"top_k": 3, "criteria": "min_voltage"})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
{"converged":true,"bus_voltages":[{"bus_id":1,"vm_pu":1.06,"va_deg":0.0},{"bus_id":2,"vm_pu":1.045,"va_deg":-4.98},{"bus_id":3,"vm_pu":1.01,"va_deg":-12.72},{"bus_id":4,"vm_pu":1.017,"va_deg":-10.33},{"bus_id":5,"vm_pu":1.02,"va_deg":-8.78},{"bus_id":6,"vm_pu":1.07,"va_deg":-14.22},{"bus_id":7,"vm_pu":1.062,"va_deg":-13.37},{"bus_id":8,"vm_pu":1.09,"va_deg":-13.36},{"bus_id":9,"vm_pu":1.056,"va_deg":-14.94},{"bus_id":10,"vm_pu":1.051,"va_deg":-15.1},{"bus_id":11,"vm_pu":1.057,"va_deg":-14.79},{"bus_id":12,"vm_pu":1.055,"va_deg":-15.08},{"bus_id":13,"vm_pu":1.05,"va_deg":-15.16},{"bus_id":14,"vm_pu":1.036,"va_deg":-16.04}],"line_flows":[{"line_id":0,"p_from_mw":156.88,"loading_percent":77.4},{"line_id":1,"p_from_mw":75.51,"loading_percent":45.1},{"line_id":2,"p_from_mw":73.24,"loading_perce …[1038 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=4.92e-04; F_MAE=5.57; faithful=0.0 %; solved=True (numeric_ok); flags=-; error=-; tokens=3140; cost_usd=0.0175; wall=6.9 s
````

**Ejemplo: no resuelto**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
{"converged":true,"bus_voltages":[{"bus_id":1,"vm_pu":1.06,"va_deg":0.0},{"bus_id":2,"vm_pu":1.045,"va_deg":-4.98},{"bus_id":3,"vm_pu":1.01,"va_deg":-12.72},{"bus_id":4,"vm_pu":1.017,"va_deg":-10.33},{"bus_id":5,"vm_pu":1.019,"va_deg":-8.78},{"bus_id":6,"vm_pu":1.07,"va_deg":-14.22},{"bus_id":7,"vm_pu":1.062,"va_deg":-13.37},{"bus_id":8,"vm_pu":1.09,"va_deg":-13.36},{"bus_id":9,"vm_pu":1.056,"va_deg":-14.94},{"bus_id":10,"vm_pu":1.051,"va_deg":-15.1},{"bus_id":11,"vm_pu":1.057,"va_deg":-14.79},{"bus_id":12,"vm_pu":1.055,"va_deg":-15.08},{"bus_id":13,"vm_pu":1.05,"va_deg":-15.16},{"bus_id":14,"vm_pu":1.036,"va_deg":-16.04}],"line_flows":[{"line_id":0,"p_from_mw":147.2,"loading_percent":52.4},{"line_id":1,"p_from_mw":71.6,"loading_percent":27.8},{"line_id":2,"p_from_mw":70.1,"loading_percent …[1014 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=3.07e-03; F_MAE=7.38; faithful=0.0 %; solved=False (voltage_error); flags=-; error=-; tokens=3125; cost_usd=0.0175; wall=6.8 s
````

**Ejemplo: primer item**

````
request (case14-multistep-002-s0, case14, difficulty=multistep, seed=1627694679): Load the 14-bus test case (case14), disconnect the line between bus 6 and bus 13, disconnect the line between bus 12 and bus 13, and finally rerun the power flow, then list every line whose loading is above 100%.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 6, "to_bus": 13}) -> disconnect_line({"from_bus": 12, "to_bus": 13}) -> run_powerflow({})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
{"converged":true,"bus_voltages":[{"bus_id":1,"vm_pu":1.06,"va_deg":0.0},{"bus_id":2,"vm_pu":1.045,"va_deg":-4.98},{"bus_id":3,"vm_pu":1.01,"va_deg":-12.72},{"bus_id":4,"vm_pu":1.017,"va_deg":-10.33},{"bus_id":5,"vm_pu":1.019,"va_deg":-8.78},{"bus_id":6,"vm_pu":1.07,"va_deg":-14.22},{"bus_id":7,"vm_pu":1.062,"va_deg":-13.37},{"bus_id":8,"vm_pu":1.09,"va_deg":-13.36},{"bus_id":9,"vm_pu":1.056,"va_deg":-14.94},{"bus_id":10,"vm_pu":1.051,"va_deg":-15.1},{"bus_id":11,"vm_pu":1.057,"va_deg":-14.79},{"bus_id":12,"vm_pu":1.055,"va_deg":-15.07},{"bus_id":13,"vm_pu":1.05,"va_deg":-15.16},{"bus_id":14,"vm_pu":1.036,"va_deg":-16.04}],"line_flows":[{"line_id":0,"p_from_mw":156.88,"loading_percent":100.2},{"line_id":1,"p_from_mw":75.51,"loading_percent":72.3},{"line_id":2,"p_from_mw":73.24,"loading_per …[1036 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=2.01e-02; F_MAE=6.66; faithful=1.4 %; solved=False (voltage_error); flags=-; error=-; tokens=3166; cost_usd=0.0176; wall=7.4 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- LLM-only: V_MAE entre 5.99e-03 (llm_only_forced:structured/case14) y 2.17e-02 (llm_only_forced:cot/case14) p.u. sobre los items que devolvieron números.
- 0.0 % (0/20) de abstención en LLM-only (respuesta con `converged=false` o arrays vacíos).
- En LLM-only, 0 items no resueltos por `convergence_mismatch` y 15 por `voltage_error`.
- 1 items con `json_parse_failed`: la respuesta LLM-only no fue JSON parseable.
- Solved más alto: `llm_only_forced:structured` 20.0 % (2/10); más bajo: `llm_only_forced:cot` 20.0 % (2/10).
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- Trazabilidad de números (Faith.) media en LLM-only: 2.1 % (sin tools, todo número es no trazable salvo los copiados de la request).
- Costo total 0.5703 USD; el método más caro fue `llm_only_forced:cot` con 0.3184 USD (56 %).

## 6. Archivos

Rutas absolutas bajo `results_validation_gpt-5.4_llm_only`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_llm_only/report.json
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_llm_only/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_llm_only/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_llm_only/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_llm_only/scoreboard_per_case.json
  traces (20 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_validation_gpt-5.4_llm_only/traces
````

