# evagent on caltech, 2026-09-28, gpt-4o-mini

Built from `ev_matrix_openrouter_openai_gpt-4o-mini_rescored` by `evaluation/postprocess.py`. No model was called to write this report.

## Outcome

| solved | escalated | wrong, unflagged | run error |
|---|---|---|---|
| 0.0 % (0/20) | 0.0 % (0/20) | 100.0 % (20/20) | 0 |

The three outcomes are exclusive and sum to the request count.

## Formulation, traceability, cost

| formulation exact (days) | traceable answers | tokens | est. cost |
|---|---|---|---|
| 0.00 % | 100.00 % | 213,684 | $0.0557 |

## Wrong and unflagged: 20

- `01_caltech-2018-09-17-unmet_question-s0` (unmet_question): failed: state, answer
- `02_caltech-2018-10-15-served_share-s0` (served_share): failed: state, answer
- `03_caltech-2018-11-05-unmet_question-s0` (unmet_question): failed: state, answer
- `04_caltech-2018-11-12-feasible_yesno-s0` (feasible_yesno): failed: state
- `05_caltech-2018-12-03-feasible_yesno-s0` (feasible_yesno): failed: state
- `06_caltech-2018-12-10-served_share-s0` (served_share): failed: state, answer
- `07_caltech-2019-01-15-served_share-s0` (served_share): failed: state, answer
- `08_caltech-2019-01-22-unmet_question-s0` (unmet_question): failed: state, answer
- `09_caltech-2019-02-20-feasible_yesno-s0` (feasible_yesno): failed: state
- `10_caltech-2019-03-10-unmet_question-s0` (unmet_question): failed: state, answer
- `11_caltech-2019-04-15-feasible_yesno-s0` (feasible_yesno): failed: state, answer
- `12_caltech-2019-04-22-served_share-s0` (served_share): failed: state, answer
- `13_caltech-2019-05-01-unmet_question-s0` (unmet_question): failed: state, answer
- `14_caltech-2019-05-08-feasible_yesno-s0` (feasible_yesno): failed: state, answer
- `15_caltech-2019-05-15-served_share-s0` (served_share): failed: state, answer
- `16_caltech-2019-05-22-unmet_question-s0` (unmet_question): failed: state
- `17_caltech-2019-06-03-feasible_yesno-s0` (feasible_yesno): failed: state
- `18_caltech-2019-06-10-served_share-s0` (served_share): failed: state, answer
- `19_caltech-2019-06-15-unmet_question-s0` (unmet_question): failed: state
- `20_caltech-2019-06-20-schedule_only-s0` (schedule_only): failed: state

## Escalated: 0

none

## Every request

| nn | request | variant | outcome | form. | trace | answer | gap % | tokens |
|---|---|---|---|---|---|---|---|---|
| 01 | `caltech-2018-09-17-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | pass | fail | 0.13 | 17668 |
| 02 | `caltech-2018-10-15-served_share-s0` | served_share | wrong_unflagged | wrong_field | pass | fail | -0.00 | 15325 |
| 03 | `caltech-2018-11-05-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | pass | fail | 0.43 | 14295 |
| 04 | `caltech-2018-11-12-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | pass | pass | -0.31 | 11932 |
| 05 | `caltech-2018-12-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | pass | pass | 0.00 | 9764 |
| 06 | `caltech-2018-12-10-served_share-s0` | served_share | wrong_unflagged | wrong_field | pass | fail | -0.01 | 10741 |
| 07 | `caltech-2019-01-15-served_share-s0` | served_share | wrong_unflagged | wrong_field | pass | fail | -1.09 | 11688 |
| 08 | `caltech-2019-01-22-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | pass | fail | 0.00 | 9945 |
| 09 | `caltech-2019-02-20-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | pass | pass | 1.23 | 11272 |
| 10 | `caltech-2019-03-10-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | pass | fail | 2.54 | 5081 |
| 11 | `caltech-2019-04-15-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | pass | fail | -0.00 | 9081 |
| 12 | `caltech-2019-04-22-served_share-s0` | served_share | wrong_unflagged | wrong_field | pass | fail | 0.50 | 10009 |
| 13 | `caltech-2019-05-01-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | pass | fail | -2.29 | 10533 |
| 14 | `caltech-2019-05-08-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | pass | fail | 0.00 | 11044 |
| 15 | `caltech-2019-05-15-served_share-s0` | served_share | wrong_unflagged | wrong_field | pass | fail | -0.33 | 10452 |
| 16 | `caltech-2019-05-22-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | pass | pass | -0.02 | 10414 |
| 17 | `caltech-2019-06-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | pass | pass | -1.51 | 9790 |
| 18 | `caltech-2019-06-10-served_share-s0` | served_share | wrong_unflagged | wrong_field | pass | fail | -0.00 | 10388 |
| 19 | `caltech-2019-06-15-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | pass | pass | -0.05 | 5904 |
| 20 | `caltech-2019-06-20-schedule_only-s0` | schedule_only | wrong_unflagged | wrong_field | pass | not_checkable | 0.00 | 8358 |
