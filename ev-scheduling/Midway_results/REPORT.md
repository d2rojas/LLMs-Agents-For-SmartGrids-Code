# Midway Results — ECE 285 EV Charging Schedule Assistant

**Group #10**: Ryan Luo, Peter Quawas

## Summary Table

| Pipeline | Date | Sessions | Cost ($) | Peak (kW) | Unmet (kWh) | Served (%) | Cost Red. (%) | Violations | Feasible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| phase_a | 2019-05-01 | 44 | 111.5657 | 50.0 | 2.587 | 97.73 | 25.55 | 1 | False |
| agent | 2019-05-01 | 44 | 111.5657 | 50.0 | 2.587 | 97.73 | 25.55 | 1 | False |
| baseline | 2019-05-01 | 44 | 53.13 | 28.0 | 424.677 | 11.36 | 64.55 | 65 | False |
| phase_a | 2019-05-15 | 43 | 77.6805 | 49.9999 | 11.2158 | 93.02 | 33.99 | 3 | False |
| agent | 2019-05-15 | 43 | 77.6805 | 49.9999 | 11.2158 | 93.02 | 33.99 | 3 | False |
| baseline | 2019-05-15 | 43 | 50.0257 | 14.584 | 298.4122 | 6.98 | 57.49 | 70 | False |
| phase_a | 2019-06-03 | 39 | 76.4003 | 49.9999 | 5.909 | 92.31 | 35.32 | 3 | False |
| agent | 2019-06-03 | 39 | 76.4003 | 49.9999 | 5.909 | 92.31 | 35.32 | 3 | False |
| baseline | 2019-06-03 | 39 | 1.7556 | 14.0 | 328.4588 | 0.0 | 98.51 | 43 | False |
| phase_a | 2019-06-15 | 15 | 37.7195 | 27.4486 | 42.756 | 86.67 | 17.51 | 2 | False |
| agent | 2019-06-15 | 15 | 37.7195 | 27.4486 | 42.756 | 86.67 | 17.51 | 2 | False |
| baseline | 2019-06-15 | 15 | 4.9241 | 7.0 | 209.711 | 0.0 | 89.23 | 16 | False |
| phase_a | 2018-11-05 | 66 | 146.1518 | 50.0 | 60.2817 | 25.76 | 27.89 | 49 | False |
| agent | 2018-11-05 | 66 | 146.1518 | 50.0 | 60.2817 | 25.76 | 27.89 | 49 | False |
| baseline | 2018-11-05 | 66 | 55.65 | 21.0 | 572.5427 | 9.09 | 72.54 | 140 | False |

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
collecting ... collected 26 items

tests/test_baseline_parse.py::test_resample_exact_divisor PASSED         [  3%]
tests/test_baseline_parse.py::test_resample_exact_match_is_identity PASSED [  7%]
tests/test_baseline_parse.py::test_resample_close_too_long_truncates PASSED [ 11%]
tests/test_baseline_parse.py::test_resample_close_too_short_pads PASSED  [ 15%]
tests/test_baseline_parse.py::test_resample_far_off_returns_none PASSED  [ 19%]
tests/test_baseline_parse.py::test_resample_48_to_96 PASSED              [ 23%]
tests/test_baseline_parse.py::test_parse_24_values_resampled_to_96 PASSED [ 26%]
tests/test_baseline_parse.py::test_parse_97_values_truncated_to_96 PASSED [ 30%]
tests/test_baseline_parse.py::test_parse_94_values_padded_to_96 PASSED   [ 34%]
tests/test_baseline_parse.py::test_parse_irrecoverable_length_skipped PASSED [ 38%]
tests/test_baseline_parse.py::test_parse_mixed_good_and_resampled PASSED [ 42%]
tests/test_constraints.py::test_check_feasible_schedule PASSED           [ 46%]
tests/test_constraints.py::test_check_availability_violation PASSED      [ 50%]
tests/test_constraints.py::test_check_per_charger_violation PASSED       [ 53%]
tests/test_constraints.py::test_check_site_cap_violation PASSED          [ 57%]
tests/test_constraints.py::test_check_energy_violation PASSED            [ 61%]
tests/test_data_loader.py::test_raw_session_to_standard PASSED           [ 65%]
tests/test_data_loader.py::test_load_sessions_with_api_returns_day_sessions PASSED [ 69%]
tests/test_faithfulness.py::test_parse_explanation_v1_template PASSED    [ 73%]
tests/test_faithfulness.py::test_parse_explanation_without_pct PASSED    [ 76%]
tests/test_faithfulness.py::test_parse_explanation_invalid_returns_none PASSED [ 80%]
tests/test_faithfulness.py::test_check_faithfulness_facts_match PASSED   [ 84%]
tests/test_faithfulness.py::test_check_faithfulness_facts_mismatch PASSED [ 88%]
tests/test_faithfulness.py::test_check_faithfulness_text_matching_ground_truth PASSED [ 92%]
tests/test_faithfulness.py::test_check_faithfulness_text_mismatch PASSED [ 96%]
tests/test_faithfulness.py::test_check_faithfulness_unparseable PASSED   [100%]

============================== 26 passed in 0.42s ==============================
```
