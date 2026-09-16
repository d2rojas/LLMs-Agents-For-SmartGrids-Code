# Informe de experimento: `results_probe_forced`

Generado el 2026-09-15 22:05 por benchmarks/experiment_report.py a partir de 2 report(s) del directorio results_probe_forced (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced
````

- Reports leídos: 2 (`report.rescored.json` usado en 0; el resto `report.json`)
- Modelos: `openrouter:openai/gpt-4o`, `openrouter:openai/gpt-4o-mini`
- Métodos: `llm_only_forced:cot`, `llm_only_forced:structured`
- Casos: `case14`, `case30`
- Requests: generadas, N=20 por caso y seed, difficulties=todas (2 reports)
- Items por dificultad: plain=40, parameterized=40, multistep=40, ambiguous=40
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-15 20:54 – 2026-09-15 20:58
- Costo total: 2.0979 USD (160 items; costo medio 0.01311 USD/item)
- Items totales: 160; ok=152; con error=8; tokens totales=771643
- Solved global: 0.6 % (1/160)

Errores por tipo:

| Tipo | Items | Métodos afectados |
|---------------------|-----|------------------------------------------------|
| json_parse_failed | 8 | llm_only_forced:cot (5), llm_only_forced:structured (3) |


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

**User prompt (primer item)** — 6461 caracteres; case=case14, seed=1911784258, k=1, request_id=case14-ambiguous-003-s0

````
You are a power systems expert. Based on the following IEEE case14 test system data, calculate the AC power flow results.

## System Data (from pandapower network tables)

### Node Data (Bus Table: net.bus)

   name    vn_kv type zone  in_service
0     1  135.000    b  1.0        True
1     2  135.000    b  1.0        True
2     3  135.000    b  1.0        True
3     4  135.000    b  1.0        True
4     5  135.000    b  1.0        True
5     6    0.208    b  1.0        True
6     7   14.000    b  1.0        True
7     8   12.000    b  1.0        True
8     9    0.208    b  1.0        True
9    10    0.208    b  1.0        True
10   11    0.208    b  1.0        True
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

**User prompt (primer item)** — 5966 caracteres; case=case14, seed=1911784258, k=1, request_id=case14-ambiguous-003-s0

````
You are a power systems expert. Based on the following IEEE case14 test system data, calculate the AC power flow results.

## System Data (from pandapower network tables)

### Node Data (Bus Table: net.bus)

   name    vn_kv type zone  in_service
0     1  135.000    b  1.0        True
1     2  135.000    b  1.0        True
2     3  135.000    b  1.0        True
3     4  135.000    b  1.0        True
4     5  135.000    b  1.0        True
5     6    0.208    b  1.0        True
6     7   14.000    b  1.0        True
7     8   12.000    b  1.0        True
8     9    0.208    b  1.0        True
9    10    0.208    b  1.0        True
10   11    0.208    b  1.0        True
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

Modelos: M1 = `openrouter:openai/gpt-4o`; M2 = `openrouter:openai/gpt-4o-mini`

| Model | Method | Case | N | Solved | Form. | V_MAE | F_MAE | FR | Faith. | SFR | Claim | Abst. | Calls | Tok. | TTV | $ |
|-----|--------------------------------|------|----|------|-----|--------|-----|-----|------|----|-----|-----|-----|----|----|------|
| M1 | llm_only_forced:cot | case14 | 20 | 5.0 | -- | 2.55e-02 | 32.02 | 100.0 | 4.6 | -- | -- | 0.0 | n/a | 3959 | 10.4 | 0.3987 |
| M1 | llm_only_forced:cot | case30 | 20 | 0.0 | -- | 1.38e-02 | 16.08 | 100.0 | 4.6 | -- | -- | 0.0 | n/a | 6280 | 15.7 | 0.6671 |
| M1 | llm_only_forced:structured | case14 | 20 | 0.0 | -- | 3.56e-02 | 29.35 | 100.0 | 3.5 | -- | -- | 0.0 | n/a | 3457 | 7.0 | 0.3247 |
| M1 | llm_only_forced:structured | case30 | 20 | 0.0 | -- | 1.42e-02 | 22.26 | 100.0 | 5.6 | -- | -- | 0.0 | n/a | 5776 | 13.0 | 0.5929 |
| M2 | llm_only_forced:cot | case14 | 20 | 0.0 | -- | 3.41e-01 | 32.40 | 100.0 | 4.6 | -- | -- | 5.0 | n/a | 3850 | 11.3 | 0.0226 |
| M2 | llm_only_forced:cot | case30 | 20 | 0.0 | -- | 2.32e-02 | 20.46 | 100.0 | 12.5 | -- | -- | 0.0 | n/a | 6178 | 19.3 | 0.0388 |
| M2 | llm_only_forced:structured | case14 | 20 | 0.0 | -- | 4.54e-01 | 31.87 | 100.0 | 1.3 | -- | -- | 0.0 | n/a | 3325 | 8.7 | 0.0179 |
| M2 | llm_only_forced:structured | case30 | 20 | 0.0 | -- | 2.04e-02 | 10.58 | 100.0 | 13.2 | -- | -- | 0.0 | n/a | 5758 | 19.8 | 0.0354 |

### Agregado por método (media ponderada por items sobre todos los casos)

Modelos: M1 = `openrouter:openai/gpt-4o`; M2 = `openrouter:openai/gpt-4o-mini`

| Model | Method | Case | N | Solved | Form. | V_MAE | F_MAE | FR | Faith. | SFR | Claim | Abst. | Calls | Tok. | TTV | $ |
|-----|--------------------------------|-------|----|------|-----|--------|-----|-----|------|----|-----|-----|-----|----|----|------|
| M1 | llm_only_forced:cot | 2 casos | 40 | 2.5 | -- | 1.96e-02 | 24.05 | 100.0 | 4.6 | -- | -- | 0.0 | n/a | 5119 | 13.0 | 1.0657 |
| M1 | llm_only_forced:structured | 2 casos | 40 | 0.0 | -- | 2.49e-02 | 25.80 | 100.0 | 4.6 | -- | -- | 0.0 | n/a | 4617 | 10.0 | 0.9175 |
| M2 | llm_only_forced:cot | 2 casos | 40 | 0.0 | -- | 1.59e-01 | 25.58 | 100.0 | 8.5 | -- | -- | 2.5 | n/a | 5014 | 15.3 | 0.0614 |
| M2 | llm_only_forced:structured | 2 casos | 40 | 0.0 | -- | 2.20e-01 | 20.36 | 100.0 | 7.2 | -- | -- | 0.0 | n/a | 4541 | 14.3 | 0.0532 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|--------------------------------|-----|----------------|---------|---------|
| llm_only_forced:cot | n/a | n/a | n/a | n/a |
| llm_only_forced:structured | n/a | n/a | n/a | n/a |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|--------------------------------|----------|----------------|----------|----------|
| llm_only_forced:cot | 5.0 (1/20) | 0.0 (0/20) | 0.0 (0/20) | 0.0 (0/20) |
| llm_only_forced:structured | 0.0 (0/20) | 0.0 (0/20) | 0.0 (0/20) | 0.0 (0/20) |

### Tipos de error de formulación (conteo de items)

| Method | unparsed |
|--------------------------------|--------|
| llm_only_forced:cot | 5 |
| llm_only_forced:structured | 3 |

### Errores de ejecución por método (conteo de items con `error`)

| Method | json_parse_failed |
|--------------------------------|---------------------|
| llm_only_forced:cot | 5 |
| llm_only_forced:structured | 3 |


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `llm_only_forced:cot`

**Ejemplo: resuelto (solved=True)**

````
request (case14-plain-012-s0, case14, difficulty=plain, seed=1683194653): Load the 14-bus test case (case14).
intended_calls: load_case({"case_name": "case14"})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
To solve the AC power flow for the IEEE 14-bus test system, we need to follow these steps:

1. **Identify Buses:**
   - Slack Bus: Bus 0 (External Grid)
   - Load Buses: Buses 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13
   - Generator Buses: Buses 1, 2, 5, 7

2. **Identify Lines/Branches:**
   - Lines: From the `net.line` table, lines are identified by their `from_bus` and `to_bus` columns.
   - Transformers: From the `net.trafo` table, transformers are identified by their `hv_bus` and `lv_bus` columns.

3. **Quantities and Units:**
   - Voltage Magnitude (p.u.) and Phase Angle (degrees) for each bus.
   - Active Power (MW) and Load Factor (%) at the beginning of each branch.

4. **Power Balance:**
   - Total generation must equal total load plus losses.
   - Ensure no voltage or line loading limi …[2535 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=8.49e-04; F_MAE=24.26; faithful=0.0 %; solved=True (numeric_ok); flags=-; error=-; tokens=3944; cost_usd=0.0199; wall=8.6 s
````

**Ejemplo: con bandera de fallo (claimed/stale/abstained)**

````
request (case14-ambiguous-007-s0, case14, difficulty=ambiguous, seed=2073320062): Load the 14-bus test case (case14) and disconnect the line between bus 6 and bus 13 (1-based).
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 6, "to_bus": 13})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
1. The request refers to the following buses:
   - Slack bus: Bus 1 (external grid)
   - Load buses: Buses 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13
   - Generator buses: Buses 1, 2, 5, 7

2. The line being disconnected is between bus 6 and bus 13, which corresponds to line_id 12 in the line data.

3. The quantities requested include:
   - Voltage magnitude (p.u.) and phase angle (degrees) for each bus
   - Active power (MW) and load factor (%) at the beginning of each branch
   - Total generation (MW), total load (MW), and total losses (MW)

4. With the disconnection of the line between bus 6 and bus 13, bus 13 will be isolated from the network. This will affect the power balance, as the loads at bus 13 will not be supplied. The total generation will need to be recalculated without the contribu …[2096 chars más]
--- Scoring ---
formulation=unparsed (exact=None); V_MAE=--; F_MAE=--; faithful=0.0 %; solved=False (run_failed); flags=abstained,abstained_on_solvable; error=json_parse_failed; tokens=3805; cost_usd=0.0011; wall=12.0 s
````

**Ejemplo: no resuelto**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
1. The request refers to the following buses:
   - Slack bus: Bus 0 (external grid)
   - Load buses: Buses 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13
   - Generator buses: Buses 1, 2, 5, 7

2. The line involved in the request is the one between bus 10 and bus 11, which is line_id 13.

3. The quantities and units requested are:
   - Voltage magnitude (p.u.) and phase angle (degrees) for each bus
   - Active power (MW) and load factor (%) at the beginning of each branch
   - Total generation (MW), total load (MW), and total losses (MW)

4. With the disconnection of the line between bus 10 and bus 11, the power flow will change, affecting the load distribution and potentially leading to changes in voltage levels and branch flows. The power balance must hold, meaning total generation must equal total …[1843 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=4.38e-01; F_MAE=37.44; faithful=0.0 %; solved=False (voltage_error); flags=-; error=-; tokens=3687; cost_usd=0.0010; wall=12.3 s
````

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
    {"bus_id": 1, "vm_pu": 1.045, "va_deg": 0.0},
    {"bus_id": 2, "vm_pu": 1.010, "va_deg": -2.0},
    {"bus_id": 3, "vm_pu": 1.020, "va_deg": -5.0},
    {"bus_id": 4, "vm_pu": 1.015, "va_deg": -3.0},
    {"bus_id": 5, "vm_pu": 1.070, "va_deg": 0.0},
    {"bus_id": 6, "vm_pu": 0.208, "va_deg": 0.0},
    {"bus_id": 7, "vm_pu": 1.090, "va_deg": 0.0},
    {"bus_id": 8, "vm_pu": 1.020, "va_deg": -1.0},
    {"bus_id": 9, "vm_pu": 0.208, "va_deg": 0.0},
    {"bus_id": 10, "vm_pu": 0.208, "va_deg": 0.0},
    {"bus_id": 11, "vm_pu": 0.208, "va_deg": 0.0},
    {"bus_id": 12, "vm_pu": 0.208, "va_deg": 0.0},
    {"bus_id": 13, "vm_pu": 0.208, "va_deg": 0.0},
    {"bus_id": 14, "vm_pu": 0.208, "va_deg": 0.0}
  ],
  "line_flows": [
    {"line_id": 0, "p_from …[997 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=4.36e-01; F_MAE=35.45; faithful=0.0 %; solved=False (voltage_error); flags=-; error=-; tokens=3293; cost_usd=0.0009; wall=10.1 s
````

**Ejemplo: primer item**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
```json
{
  "converged": true,
  "bus_voltages": [
    {"bus_id": 1, "vm_pu": 1.045, "va_deg": 0.0},
    {"bus_id": 2, "vm_pu": 1.010, "va_deg": -4.98},
    {"bus_id": 3, "vm_pu": 1.070, "va_deg": -12.72},
    {"bus_id": 4, "vm_pu": 1.090, "va_deg": -10.33},
    {"bus_id": 5, "vm_pu": 1.070, "va_deg": -8.78},
    {"bus_id": 6, "vm_pu": 1.020, "va_deg": -14.22},
    {"bus_id": 7, "vm_pu": 1.090, "va_deg": -13.37},
    {"bus_id": 8, "vm_pu": 1.020, "va_deg": -13.97},
    {"bus_id": 9, "vm_pu": 1.010, "va_deg": -14.56},
    {"bus_id": 10, "vm_pu": 1.010, "va_deg": -15.12},
    {"bus_id": 11, "vm_pu": 1.010, "va_deg": -15.67},
    {"bus_id": 12, "vm_pu": 1.010, "va_deg": -16.21},
    {"bus_id": 13, "vm_pu": 1.010, "va_deg": -16.74},
    {"bus_id": 14, "vm_pu": 1.010, "va_deg": -17.26}
  ],
  " …[1408 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=4.36e-02; F_MAE=26.09; faithful=0.0 %; solved=False (voltage_error); flags=-; error=-; tokens=3440; cost_usd=0.0162; wall=8.9 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- LLM-only: V_MAE entre 1.38e-02 (llm_only_forced:cot/case30) y 4.54e-01 (llm_only_forced:structured/case14) p.u. sobre los items que devolvieron números.
- 0.6 % (1/160) de abstención en LLM-only (respuesta con `converged=false` o arrays vacíos).
- En LLM-only, 0 items no resueltos por `convergence_mismatch` y 139 por `voltage_error`.
- 8 items con `json_parse_failed`: la respuesta LLM-only no fue JSON parseable.
- Solved más alto: `llm_only_forced:cot` 1.2 % (1/80); más bajo: `llm_only_forced:structured` 0.0 % (0/80).
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- Trazabilidad de números (Faith.) media en LLM-only: 6.2 % (sin tools, todo número es no trazable salvo los copiados de la request).
- Costo total 2.0979 USD; el método más caro fue `llm_only_forced:cot` con 1.1272 USD (54 %).
- Solved por modelo: `openrouter:openai/gpt-4o` 1.2 % (1/80); `openrouter:openai/gpt-4o-mini` 0.0 % (0/80).

## 6. Archivos

Rutas absolutas bajo `results_probe_forced`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o-mini/report.json
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o-mini/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o-mini/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o-mini/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o-mini/scoreboard_per_case.json
  traces (80 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o-mini/traces
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o/report.json
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o/scoreboard_per_case.json
  traces (80 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/openai_gpt-4o/traces
log: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/logs/openai_gpt-4o-mini.log
log: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_forced/logs/openai_gpt-4o.log
````

