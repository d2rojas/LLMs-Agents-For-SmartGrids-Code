# Midway Results — ECE 285 EV Charging Schedule Assistant

**Group #10**: Ryan Luo, Peter Quawas

## Summary Table

| Pipeline | Date | Sessions | Cost ($) | Peak (kW) | Unmet (kWh) | Served (%) | Cost Red. (%) | Violations | Feasible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| phase_a | 2019-05-01 | 44 | 111.5657 | 50.0 | 2.587 | 97.73 | 25.55 | 1 | False |
| agent | 2019-05-01 | 44 | 111.5657 | 50.0 | 2.587 | 97.73 | 25.55 | 1 | False |
| baseline | 2019-05-01 | 44 | 57.12 | 28.0 | 390.127 | 11.36 | 61.88 | 69 | False |
| phase_a | 2019-05-15 | 43 | 77.6805 | 49.9999 | 11.2158 | 93.02 | 33.99 | 3 | False |
| agent | 2019-05-15 | 43 | 77.6805 | 49.9999 | 11.2158 | 93.02 | 33.99 | 3 | False |
| baseline | 2019-05-15 | 43 | 55.44 | 49.0 | 242.6302 | 23.26 | 52.89 | 56 | False |
| phase_a | 2019-06-03 | 39 | 76.4003 | 49.9999 | 5.909 | 92.31 | 35.32 | 3 | False |
| agent | 2019-06-03 | 39 | 76.4003 | 49.9999 | 5.909 | 92.31 | 35.32 | 3 | False |
| baseline | 2019-06-03 | 39 | 0.69 | 7.0 | 337.339 | 0.0 | 99.42 | 39 | False |
| phase_a | 2019-06-15 | 15 | 37.7195 | 27.4486 | 42.756 | 86.67 | 17.51 | 2 | False |
| agent | 2019-06-15 | 15 | 37.7195 | 27.4486 | 42.756 | 86.67 | 17.51 | 2 | False |
| baseline | 2019-06-15 | 15 | 3.1445 | 7.0 | 219.7288 | 0.0 | 93.12 | 16 | False |
| phase_a | 2018-11-05 | 66 | 146.1518 | 50.0 | 60.2817 | 25.76 | 27.89 | 49 | False |
| agent | 2018-11-05 | 66 | 146.1518 | 50.0 | 60.2817 | 25.76 | 27.89 | 49 | False |
| baseline | 2018-11-05 | 66 | 90.72 | 28.0 | 568.6677 | 12.12 | 55.24 | 165 | False |

## Plots

Schedule heatmaps and load profiles are saved as PNG files in this directory.
Each file is named `<pipeline>_<date>_schedule.png` or `<pipeline>_<date>_load.png`.

- `agent_2018-11-05_load.png`
- `agent_2018-11-05_schedule.png`
- `agent_2019-05-01_load.png`
- `agent_2019-05-01_schedule.png`
- `agent_2019-05-15_load.png`
- `agent_2019-05-15_schedule.png`
- `agent_2019-06-03_load.png`
- `agent_2019-06-03_schedule.png`
- `agent_2019-06-15_load.png`
- `agent_2019-06-15_schedule.png`
- `baseline_2018-11-05_load.png`
- `baseline_2018-11-05_schedule.png`
- `baseline_2019-05-01_load.png`
- `baseline_2019-05-01_schedule.png`
- `baseline_2019-05-15_load.png`
- `baseline_2019-05-15_schedule.png`
- `baseline_2019-06-03_load.png`
- `baseline_2019-06-03_schedule.png`
- `baseline_2019-06-15_load.png`
- `baseline_2019-06-15_schedule.png`
- `phase_a_2018-11-05_load.png`
- `phase_a_2018-11-05_schedule.png`
- `phase_a_2019-05-01_load.png`
- `phase_a_2019-05-01_schedule.png`
- `phase_a_2019-05-15_load.png`
- `phase_a_2019-05-15_schedule.png`
- `phase_a_2019-06-03_load.png`
- `phase_a_2019-06-03_schedule.png`
- `phase_a_2019-06-15_load.png`
- `phase_a_2019-06-15_schedule.png`

## Agent Explanations

### agent_2018-11-05_explanation

> Total cost: $146.15. Peak load: 50.0 kW. Unmet energy: 60.28 kWh. Cost reduction vs uncontrolled: 27.9%.

### agent_2019-05-01_explanation

> Total cost: $111.57. Peak load: 50.0 kW. Unmet energy: 2.59 kWh. Cost reduction vs uncontrolled: 25.6%.

### agent_2019-05-15_explanation

> Total cost: $77.68. Peak load: 50.0 kW. Unmet energy: 11.22 kWh. Cost reduction vs uncontrolled: 34.0%.

### agent_2019-06-03_explanation

> Total cost: $76.40. Peak load: 50.0 kW. Unmet energy: 5.91 kWh. Cost reduction vs uncontrolled: 35.3%.

### agent_2019-06-15_explanation

> Total cost: $37.72. Peak load: 27.4 kW. Unmet energy: 42.76 kWh. Cost reduction vs uncontrolled: 17.5%.

## Unit Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.13.1, pytest-9.0.2, pluggy-1.6.0 -- /Users/pete/Desktop/WI26/285/Project/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/pete/Desktop/WI26/285/Project
plugins: anyio-4.12.1
collecting ... collected 7 items

tests/test_constraints.py::test_check_feasible_schedule PASSED           [ 14%]
tests/test_constraints.py::test_check_availability_violation PASSED      [ 28%]
tests/test_constraints.py::test_check_per_charger_violation PASSED       [ 42%]
tests/test_constraints.py::test_check_site_cap_violation PASSED          [ 57%]
tests/test_constraints.py::test_check_energy_violation PASSED            [ 71%]
tests/test_data_loader.py::test_raw_session_to_standard PASSED           [ 85%]
tests/test_data_loader.py::test_load_sessions_with_api_returns_day_sessions PASSED [100%]

============================== 7 passed in 0.56s ===============================
```
