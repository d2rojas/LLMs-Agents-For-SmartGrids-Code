# Midway Results — Structured Tables

**Source:** `Midway_results/metrics_summary.csv`  
**Benchmark:** 5 dates, 3 pipelines (Phase A, Agent, Baseline). Site: Caltech. Config: 50 kW cap, default TOU.

---

## 1. Full results (all runs)

| Pipeline | Date       | Sessions | Cost ($) | Peak (kW) | Unmet (kWh) | Served (%) | Cost red. (%) | Violations | Feasible |
|----------|------------|----------|----------|-----------|-------------|------------|---------------|------------|----------|
| phase_a  | 2019-05-01 | 44       | 111.57   | 50.0      | 2.59        | 97.7       | 25.6          | 1          | No       |
| agent    | 2019-05-01 | 44       | 111.57   | 50.0      | 2.59        | 97.7       | 25.6          | 1          | No       |
| baseline | 2019-05-01 | 44       | 53.13    | 28.0      | 424.68      | 11.4       | 64.6          | 65         | No       |
| phase_a  | 2019-05-15 | 43       | 77.68    | 50.0      | 11.22       | 93.0       | 34.0          | 3          | No       |
| agent    | 2019-05-15 | 43       | 77.68    | 50.0      | 11.22       | 93.0       | 34.0          | 3          | No       |
| baseline | 2019-05-15 | 43       | 50.03    | 14.6      | 298.41      | 7.0        | 57.5          | 70         | No       |
| phase_a  | 2019-06-03 | 39       | 76.40    | 50.0      | 5.91        | 92.3       | 35.3          | 3          | No       |
| agent    | 2019-06-03 | 39       | 76.40    | 50.0      | 5.91        | 92.3       | 35.3          | 3          | No       |
| baseline | 2019-06-03 | 39       | 1.76     | 14.0      | 328.46      | 0.0        | 98.5          | 43         | No       |
| phase_a  | 2019-06-15 | 15       | 37.72    | 27.4      | 42.76       | 86.7       | 17.5          | 2          | No       |
| agent    | 2019-06-15 | 15       | 37.72    | 27.4      | 42.76       | 86.7       | 17.5          | 2          | No       |
| baseline | 2019-06-15 | 15       | 4.92     | 7.0       | 209.71      | 0.0        | 89.2          | 16         | No       |
| phase_a  | 2018-11-05 | 66       | 146.15   | 50.0      | 60.28       | 25.8       | 27.9          | 49         | No       |
| agent    | 2018-11-05 | 66       | 146.15   | 50.0      | 60.28       | 25.8       | 27.9          | 49         | No       |
| baseline | 2018-11-05 | 66       | 55.65    | 21.0      | 572.54      | 9.1        | 72.5          | 140        | No       |

---

## 2. By pipeline (summary over 5 days)

| Pipeline | Cost ($) range | Peak (kW) range | Unmet (kWh) range | Served (%) range | Cost red. (%) range | Violations (total) |
|----------|----------------|-----------------|-------------------|------------------|---------------------|---------------------|
| Phase A  | 37.72 – 146.15 | 27.4 – 50.0     | 2.59 – 60.28      | 25.8 – 97.7      | 17.5 – 35.3         | 58                  |
| Agent    | 37.72 – 146.15 | 27.4 – 50.0     | 2.59 – 60.28      | 25.8 – 97.7      | 17.5 – 35.3         | 58                  |
| Baseline | 1.76 – 55.65   | 7.0 – 28.0      | 209.71 – 572.54   | 0.0 – 11.4       | 57.5 – 98.5         | 334                 |

---

## 3. By date (one row per date, Phase A / Agent only — they match)

| Date       | Sessions | Cost ($) | Peak (kW) | Unmet (kWh) | Served (%) | Cost red. (%) |
|------------|----------|----------|-----------|-------------|------------|----------------|
| 2019-05-01 | 44       | 111.57  | 50.0      | 2.59        | 97.7       | 25.6           |
| 2019-05-15 | 43       | 77.68   | 50.0      | 11.22       | 93.0       | 34.0           |
| 2019-06-03 | 39       | 76.40   | 50.0      | 5.91        | 92.3       | 35.3           |
| 2019-06-15 | 15       | 37.72   | 27.4      | 42.76       | 86.7       | 17.5           |
| 2018-11-05 | 66       | 146.15  | 50.0      | 60.28       | 25.8       | 27.9           |

---

## 4. Baseline vs Phase A (same dates)

| Date       | Phase A cost ($) | Baseline cost ($) | Phase A served (%) | Baseline served (%) | Baseline violations |
|------------|------------------|-------------------|--------------------|---------------------|----------------------|
| 2019-05-01 | 111.57           | 53.13             | 97.7               | 11.4                | 65                   |
| 2019-05-15 | 77.68            | 50.03             | 93.0               | 7.0                 | 70                   |
| 2019-06-03 | 76.40            | 1.76              | 92.3               | 0.0                 | 43                   |
| 2019-06-15 | 37.72            | 4.92              | 86.7               | 0.0                 | 16                   |
| 2018-11-05 | 146.15           | 55.65             | 25.8               | 9.1                 | 140                  |

*Note: Baseline often has lower cost because much demand is unmet (schedule zeros or partial); high violations and low % served.*

---

**Column key**

- **Cost:** Total energy cost (USD).  
- **Peak:** Max total power (kW) over the day.  
- **Unmet:** Total kWh not delivered to sessions.  
- **Served (%):** % of sessions that received ≥ requested energy.  
- **Cost red. (%):** % cost reduction vs uncontrolled (charge-asap) baseline.  
- **Violations:** Count of constraint violations from the checker.
