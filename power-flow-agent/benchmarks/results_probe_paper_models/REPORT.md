# Informe de experimento: `results_probe_paper_models`

Generado el 2026-09-15 22:05 por benchmarks/experiment_report.py a partir de 3 report(s) del directorio results_probe_paper_models (ruta completa en la sección 1). Prosa en español; identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.

## 1. Qué se corrió

Directorio analizado:

````
/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models
````

- Reports leídos: 3 (`report.rescored.json` usado en 0; el resto `report.json`)
- Modelos: `openrouter:anthropic/claude-opus-4.7`, `openrouter:openai/gpt-5.4`, `openrouter:openai/gpt-5.5`
- Métodos: `llm_only:structured`, `llm_only_forced:structured`
- Casos: `case14`, `case30`
- Requests: generadas, N=10 por caso y seed, difficulties=todas (3 reports)
- Items por dificultad: plain=36, parameterized=36, multistep=24, ambiguous=24
- runs por item: 1; k (perturbación ±10 %·k): 1; seeds: [0]; max_rounds: 8; temperature: 0.0; timeout_s: 90.0
- Fecha de la corrida (mtime de report.json): 2026-09-15 21:18 – 2026-09-15 21:30
- Costo total: 4.8052 USD (120 items; costo medio 0.04004 USD/item)
- Items totales: 120; ok=77; con error=43; tokens totales=384713
- Solved global: 15.0 % (18/120)

Errores por tipo:

| Tipo | Items | Métodos afectados |
|------------------------------------------------|-----|------------------------------------------------|
| APIStatusError 402 (sin crédito en el proveedor) | 41 | llm_only_forced:structured (26), llm_only:structured (15) |
| json_parse_failed | 2 | llm_only_forced:structured (2) |


## 2. Prompts usados

Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras 12 líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo.

### Método `llm_only:structured`

**System prompt** — 439 caracteres; strategy=structured, forced=False, sin herramientas

````
You are a power system analysis expert. You need to calculate AC power flow results based on test system data provided by the user.

Important Constraints:

- You must strictly output JSON (no extra text, no Markdown blocks).

- Do not output NaN/Infinity; all values must be finite real numbers.

- If you cannot complete the calculation, set `converged` to false and output the structure you can provide (an empty array is acceptable).
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

Modelos: M1 = `openrouter:anthropic/claude-opus-4.7`; M2 = `openrouter:openai/gpt-5.4`; M3 = `openrouter:openai/gpt-5.5`

| Model | Method | Case | N | Solved | Form. | V_MAE | F_MAE | FR | Faith. | SFR | Claim | Abst. | Calls | Tok. | TTV | $ |
|-----|--------------------------------|------|----|------|-----|--------|-----|-----|------|----|-----|-----|-----|-----|-----|------|
| M1 | llm_only:structured | case14 | 10 | 60.0 | -- | 3.73e-03 | 4.59 | 100.0 | 0.7 | -- | -- | 0.0 | n/a | 3750 | 14.0 | 0.4395 |
| M1 | llm_only:structured | case30 | 10 | 0.0 | -- | 6.90e-03 | 12.37 | 100.0 | 3.1 | -- | -- | 0.0 | n/a | 6060 | 25.9 | 0.8031 |
| M1 | llm_only_forced:structured | case14 | 10 | 50.0 | -- | 3.80e-03 | 4.24 | 100.0 | 0.1 | -- | -- | 0.0 | n/a | 3779 | 13.7 | 0.4394 |
| M1 | llm_only_forced:structured | case30 | 10 | 0.0 | -- | 5.69e-03 | 12.49 | 100.0 | 0.7 | -- | -- | 0.0 | n/a | 6105 | 26.0 | 0.0810 |
| M2 | llm_only:structured | case14 | 10 | 0.0 | -- | -- | -- | 0.0 | 0.0 | -- | -- | 70.0 | n/a | 2467 | 1.6 | 0.0678 |
| M2 | llm_only:structured | case30 | 10 | 0.0 | -- | -- | -- | 0.0 | 0.0 | -- | -- | 100.0 | n/a | 3771 | 1.5 | 0.1004 |
| M2 | llm_only_forced:structured | case14 | 10 | 40.0 | -- | 8.02e-03 | 7.86 | 100.0 | 0.1 | -- | -- | 0.0 | n/a | 3216 | 7.0 | 0.1769 |
| M2 | llm_only_forced:structured | case30 | 10 | 0.0 | -- | 1.24e-02 | 9.69 | 100.0 | 4.4 | -- | -- | 0.0 | n/a | 5297 | 11.1 | 0.3260 |
| M3 | llm_only:structured | case14 | 10 | 20.0 | -- | 2.34e-03 | 1.01 | 100.0 | 0.0 | -- | -- | 0.0 | n/a | 11941 | 121.6 | 1.4894 |
| M3 | llm_only:structured | case30 | 10 | 0.0 | -- | -- | -- | -- | -- | -- | -- | 0.0 | n/a | -- | -- | -- |
| M3 | llm_only_forced:structured | case14 | 10 | 10.0 | -- | 2.79e-03 | 1.26 | 100.0 | 0.0 | -- | -- | 0.0 | n/a | 11840 | 91.3 | 0.8816 |
| M3 | llm_only_forced:structured | case30 | 10 | 0.0 | -- | -- | -- | -- | -- | -- | -- | 0.0 | n/a | -- | -- | -- |

### Agregado por método (media ponderada por items sobre todos los casos)

Modelos: M1 = `openrouter:anthropic/claude-opus-4.7`; M2 = `openrouter:openai/gpt-5.4`; M3 = `openrouter:openai/gpt-5.5`

| Model | Method | Case | N | Solved | Form. | V_MAE | F_MAE | FR | Faith. | SFR | Claim | Abst. | Calls | Tok. | TTV | $ |
|-----|--------------------------------|-------|----|------|-----|--------|-----|-----|------|----|-----|-----|-----|-----|-----|------|
| M1 | llm_only:structured | 2 casos | 20 | 30.0 | -- | 5.32e-03 | 8.48 | 100.0 | 1.9 | -- | -- | 0.0 | n/a | 4905 | 19.9 | 1.2426 |
| M1 | llm_only_forced:structured | 2 casos | 20 | 25.0 | -- | 3.97e-03 | 4.99 | 100.0 | 0.4 | -- | -- | 0.0 | n/a | 4942 | 19.8 | 0.5204 |
| M2 | llm_only:structured | 2 casos | 20 | 0.0 | -- | -- | -- | 0.0 | 0.0 | -- | -- | 85.0 | n/a | 3119 | 1.5 | 0.1682 |
| M2 | llm_only_forced:structured | 2 casos | 20 | 20.0 | -- | 9.98e-03 | 8.67 | 100.0 | 2.3 | -- | -- | 0.0 | n/a | 4256 | 9.0 | 0.5029 |
| M3 | llm_only:structured | 2 casos | 20 | 10.0 | -- | 2.34e-03 | 1.01 | 100.0 | 0.0 | -- | -- | 0.0 | n/a | 11941 | 121.6 | 1.4894 |
| M3 | llm_only_forced:structured | 2 casos | 20 | 5.0 | -- | 2.79e-03 | 1.26 | 100.0 | 0.0 | -- | -- | 0.0 | n/a | 11840 | 91.3 | 0.8816 |

### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)

| Method | plain | parameterized | multistep | ambiguous |
|--------------------------------|-----|----------------|---------|---------|
| llm_only:structured | n/a | n/a | n/a | n/a |
| llm_only_forced:structured | n/a | n/a | n/a | n/a |

### Solved por dificultad (%, items resueltos / items)

| Method | plain | parameterized | multistep | ambiguous |
|--------------------------------|-------------|----------------|-------------|----------|
| llm_only:structured | 22.2 (4/18) | 16.7 (3/18) | 8.3 (1/12) | 0.0 (0/12) |
| llm_only_forced:structured | 27.8 (5/18) | 16.7 (3/18) | 16.7 (2/12) | 0.0 (0/12) |

### Tipos de error de formulación (conteo de items)

| Method | unparsed |
|--------------------------------|--------|
| llm_only_forced:structured | 2 |

### Errores de ejecución por método (conteo de items con `error`)

| Method | APIStatusError 402 (sin crédito en el proveedor) | json_parse_failed |
|--------------------------------|------------------------------------------------|---------------------|
| llm_only:structured | 15 | 0 |
| llm_only_forced:structured | 26 | 2 |


## 4. Trazas de ejemplo

Hasta 3 items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo (claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a 300 caracteres, salidas de tools a 300, respuesta final a 800. Se lee la traza completa de `traces/` cuando existe.

### Método `llm_only:structured`

**Ejemplo: resuelto (solved=True)**

````
request (case14-multistep-006-s0, case14, difficulty=multistep, seed=556019486): Load the 14-bus test case (case14), set the active load at bus 4 to 42.7 MW, disconnect the line between bus 3 and bus 4, reconnect the line between bus 3 and bus 4, and finally rerun the power flow, then list every line whose loading is above 80%.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 4, "p_mw": 42.7}) -> disconnect_line({"from_bus": 3, "to_bus": 4}) -> reconnect_line({"from_bus": 3, "to_bus": 4}) -> run_powerflow({})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
{
"converged": true,
"bus_voltages": [
{"bus_id": 1, "vm_pu": 1.060, "va_deg": 0.0},
{"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.98},
{"bus_id": 3, "vm_pu": 1.010, "va_deg": -12.72},
{"bus_id": 4, "vm_pu": 1.018, "va_deg": -10.33},
{"bus_id": 5, "vm_pu": 1.020, "va_deg": -8.78},
{"bus_id": 6, "vm_pu": 1.070, "va_deg": -14.22},
{"bus_id": 7, "vm_pu": 1.062, "va_deg": -14.94},
{"bus_id": 8, "vm_pu": 1.090, "va_deg": -13.36},
{"bus_id": 9, "vm_pu": 1.056, "va_deg": -14.94},
{"bus_id": 10, "vm_pu": 1.051, "va_deg": -15.10},
{"bus_id": 11, "vm_pu": 1.057, "va_deg": -14.79},
{"bus_id": 12, "vm_pu": 1.055, "va_deg": -15.08},
{"bus_id": 13, "vm_pu": 1.050, "va_deg": -15.16},
{"bus_id": 14, "vm_pu": 1.036, "va_deg": -16.04}
],
"line_flows": [
{"line_id": 0, "p_from_mw": 157.2, "loading_percent": 68. …[1249 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=3.45e-04; F_MAE=5.25; faithful=4.2 %; solved=True (numeric_ok); flags=-; error=-; tokens=3800; cost_usd=0.0442; wall=14.0 s
````

**Ejemplo: con bandera de fallo (claimed/stale/abstained)**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
{"converged":false,"bus_voltages":[],"line_flows":[],"total_generation_mw":0.0,"total_load_mw":0.0,"total_loss_mw":0.0}
--- Scoring ---
formulation=n/a (exact=None); V_MAE=--; F_MAE=--; faithful=0.0 %; solved=False (convergence_mismatch); flags=abstained,abstained_on_solvable; error=-; tokens=2450; cost_usd=0.0067; wall=1.5 s
````

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
{"bus_id": 1, "vm_pu": 1.060, "va_deg": 0.0},
{"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.98},
{"bus_id": 3, "vm_pu": 1.010, "va_deg": -12.72},
{"bus_id": 4, "vm_pu": 1.018, "va_deg": -10.31},
{"bus_id": 5, "vm_pu": 1.020, "va_deg": -8.78},
{"bus_id": 6, "vm_pu": 1.070, "va_deg": -14.22},
{"bus_id": 7, "vm_pu": 1.062, "va_deg": -14.94},
{"bus_id": 8, "vm_pu": 1.090, "va_deg": -13.36},
{"bus_id": 9, "vm_pu": 1.056, "va_deg": -14.94},
{"bus_id": 10, "vm_pu": 1.051, "va_deg": -15.10},
{"bus_id": 11, "vm_pu": 1.057, "va_deg": -14.79},
{"bus_id": 12, "vm_pu": 1.055, "va_deg": -14.94},
{"bus_id": 13, "vm_pu": 1.050, "va_deg": -15.16},
{"bus_id": 14, "vm_pu": 1.036, "va_deg": -16.05}
],
"line_flows": [
{"line_id": 0, "p_from_mw": 156.9, "loading_percent": 68. …[1242 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=3.21e-03; F_MAE=2.74; faithful=0.0 %; solved=False (voltage_error); flags=-; error=-; tokens=3730; cost_usd=0.0439; wall=13.9 s
````

### Método `llm_only_forced:structured`

**Ejemplo: resuelto (solved=True)**

````
request (case14-multistep-006-s0, case14, difficulty=multistep, seed=556019486): Load the 14-bus test case (case14), set the active load at bus 4 to 42.7 MW, disconnect the line between bus 3 and bus 4, reconnect the line between bus 3 and bus 4, and finally rerun the power flow, then list every line whose loading is above 80%.
intended_calls: load_case({"case_name": "case14"}) -> modify_load({"bus_id": 4, "p_mw": 42.7}) -> disconnect_line({"from_bus": 3, "to_bus": 4}) -> reconnect_line({"from_bus": 3, "to_bus": 4}) -> run_powerflow({})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
{"converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.060, "va_deg": 0.0}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.98}, {"bus_id": 3, "vm_pu": 1.010, "va_deg": -12.72}, {"bus_id": 4, "vm_pu": 1.018, "va_deg": -10.33}, {"bus_id": 5, "vm_pu": 1.020, "va_deg": -8.78}, {"bus_id": 6, "vm_pu": 1.070, "va_deg": -14.22}, {"bus_id": 7, "vm_pu": 1.062, "va_deg": -13.37}, {"bus_id": 8, "vm_pu": 1.090, "va_deg": -13.37}, {"bus_id": 9, "vm_pu": 1.056, "va_deg": -14.94}, {"bus_id": 10, "vm_pu": 1.051, "va_deg": -15.10}, {"bus_id": 11, "vm_pu": 1.057, "va_deg": -14.79}, {"bus_id": 12, "vm_pu": 1.055, "va_deg": -15.08}, {"bus_id": 13, "vm_pu": 1.050, "va_deg": -15.16}, {"bus_id": 14, "vm_pu": 1.036, "va_deg": -16.04}], "line_flows": [{"line_id": 0, "p_from_mw": 156.9, "loading_percent": 68.5}, …[1238 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=3.45e-04; F_MAE=2.95; faithful=0.0 %; solved=True (numeric_ok); flags=-; error=-; tokens=3826; cost_usd=0.0441; wall=13.7 s
````

**Ejemplo: no resuelto**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
{"converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.060, "va_deg": 0.0}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.98}, {"bus_id": 3, "vm_pu": 1.010, "va_deg": -12.72}, {"bus_id": 4, "vm_pu": 1.018, "va_deg": -10.33}, {"bus_id": 5, "vm_pu": 1.020, "va_deg": -8.78}, {"bus_id": 6, "vm_pu": 1.070, "va_deg": -14.22}, {"bus_id": 7, "vm_pu": 1.062, "va_deg": -13.37}, {"bus_id": 8, "vm_pu": 1.090, "va_deg": -13.37}, {"bus_id": 9, "vm_pu": 1.056, "va_deg": -14.95}, {"bus_id": 10, "vm_pu": 1.051, "va_deg": -15.11}, {"bus_id": 11, "vm_pu": 1.057, "va_deg": -14.81}, {"bus_id": 12, "vm_pu": 1.055, "va_deg": -15.09}, {"bus_id": 13, "vm_pu": 1.050, "va_deg": -15.16}, {"bus_id": 14, "vm_pu": 1.036, "va_deg": -16.05}], "line_flows": [{"line_id": 0, "p_from_mw": 156.9, "loading_percent": 68.5}, …[1237 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=3.21e-03; F_MAE=3.45; faithful=0.0 %; solved=False (voltage_error); flags=-; error=-; tokens=3756; cost_usd=0.0438; wall=13.5 s
````

**Ejemplo: primer item**

````
request (case14-ambiguous-003-s0, case14, difficulty=ambiguous, seed=1911784258): Load case14 and disconnect the line between bus ten and bus eleven.
intended_calls: load_case({"case_name": "case14"}) -> disconnect_line({"from_bus": 10, "to_bus": 11})
executed_calls: (sin etapa de tools)
fuente de la traza: archivo de traza completo
(sin rondas de herramientas: una sola llamada al LLM)
--- Respuesta final ---
{"converged":true,"bus_voltages":[{"bus_id":1,"vm_pu":1.06,"va_deg":0.0},{"bus_id":2,"vm_pu":1.045,"va_deg":-4.98},{"bus_id":3,"vm_pu":1.01,"va_deg":-12.72},{"bus_id":4,"vm_pu":1.017,"va_deg":-10.33},{"bus_id":5,"vm_pu":1.019,"va_deg":-8.78},{"bus_id":6,"vm_pu":1.07,"va_deg":-14.22},{"bus_id":7,"vm_pu":1.09,"va_deg":-13.37},{"bus_id":8,"vm_pu":1.062,"va_deg":-13.36},{"bus_id":9,"vm_pu":1.09,"va_deg":-14.94},{"bus_id":10,"vm_pu":1.051,"va_deg":-15.1},{"bus_id":11,"vm_pu":1.056,"va_deg":-14.79},{"bus_id":12,"vm_pu":1.055,"va_deg":-15.07},{"bus_id":13,"vm_pu":1.05,"va_deg":-15.16},{"bus_id":14,"vm_pu":1.036,"va_deg":-16.04}],"line_flows":[{"line_id":0,"p_from_mw":156.88,"loading_percent":49.6},{"line_id":1,"p_from_mw":75.51,"loading_percent":30.1},{"line_id":2,"p_from_mw":73.24,"loading_perce …[1033 chars más]
--- Scoring ---
formulation=n/a (exact=None); V_MAE=9.57e-03; F_MAE=5.30; faithful=0.0 %; solved=False (voltage_error); flags=-; error=-; tokens=3200; cost_usd=0.0177; wall=7.0 s
````


## 5. Lecturas

Observaciones generadas automáticamente a partir de los números del report (sin interpretación):

- LLM-only: V_MAE entre 2.34e-03 (llm_only:structured/case14) y 1.24e-02 (llm_only_forced:structured/case30) p.u. sobre los items que devolvieron números.
- 14.2 % (17/120) de abstención en LLM-only (respuesta con `converged=false` o arrays vacíos).
- Abstención con cláusula de escape: 28.3 % (17/60); sin cláusula (forced): 0.0 % (0/60).
- En LLM-only, 20 items no resueltos por `convergence_mismatch` y 39 por `voltage_error`.
- 41 items fallaron por crédito: APIStatusError 402 (sin crédito en el proveedor); cuentan como no resueltos (`run_failed`).
- 2 items con `json_parse_failed`: la respuesta LLM-only no fue JSON parseable.
- Solved más alto: `llm_only_forced:structured` 16.7 % (10/60); más bajo: `llm_only:structured` 13.3 % (8/60).
- Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).
- Trazabilidad de números (Faith.) media en LLM-only: 1.1 % (sin tools, todo número es no trazable salvo los copiados de la request).
- Costo total 4.8051 USD; el método más caro fue `llm_only:structured` con 2.9002 USD (60 %).
- Solved por modelo: `openrouter:anthropic/claude-opus-4.7` 27.5 % (11/40); `openrouter:openai/gpt-5.4` 10.0 % (4/40); `openrouter:openai/gpt-5.5` 7.5 % (3/40).

## 6. Archivos

Rutas absolutas bajo `results_probe_paper_models`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.

````
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/anthropic_claude-opus-4.7/report.json
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/anthropic_claude-opus-4.7/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/anthropic_claude-opus-4.7/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/anthropic_claude-opus-4.7/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/anthropic_claude-opus-4.7/scoreboard_per_case.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/anthropic_claude-opus-4.7/traces
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.4/report.json
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.4/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.4/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.4/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.4/scoreboard_per_case.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.4/traces
report: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.5/report.json
  scoreboard.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.5/scoreboard.json
  scoreboard.csv: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.5/scoreboard.csv
  scoreboard.md: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.5/scoreboard.md
  scoreboard_per_case.json: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.5/scoreboard_per_case.json
  traces (40 archivos): /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/openai_gpt-5.5/traces
log: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/logs/anthropic_claude-opus-4.7.log
log: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/logs/openai_gpt-5.4.log
log: /Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/03-codigo-casos-estudio/LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks/results_probe_paper_models/logs/openai_gpt-5.5.log
````

