# charge_asap on caltech, 2026-09-21, no-llm

Built from `ev_matrix_openrouter_openai_gpt-4o-mini_v2` by `evaluation/postprocess.py`. No model was called to write this report.

## Outcome

| solved | escalated | wrong, unflagged | run error |
|---|---|---|---|
| 0.0 % (0/20) | 0.0 % (0/20) | 100.0 % (20/20) | 0 |

The three outcomes are exclusive and sum to the request count.

## Formulation, traceability, cost

| formulation exact (days) | traceable answers | tokens | est. cost |
|---|---|---|---|
| - % | - % | 0 | $0.0000 |

## Wrong and unflagged: 20

- `01_caltech-2018-09-17-unmet_question-s0` (unmet_question): failed: state, answer
- `02_caltech-2018-10-15-served_share-s0` (served_share): failed: state, answer
- `03_caltech-2018-11-05-unmet_question-s0` (unmet_question): failed: state, answer
- `04_caltech-2018-11-12-feasible_yesno-s0` (feasible_yesno): failed: state
- `05_caltech-2018-12-03-feasible_yesno-s0` (feasible_yesno): failed: state
- `06_caltech-2018-12-10-served_share-s0` (served_share): failed: state
- `07_caltech-2019-01-15-served_share-s0` (served_share): failed: state, answer
- `08_caltech-2019-01-22-unmet_question-s0` (unmet_question): failed: state, answer
- `09_caltech-2019-02-20-feasible_yesno-s0` (feasible_yesno): failed: state
- `10_caltech-2019-03-10-unmet_question-s0` (unmet_question): failed: state
- `11_caltech-2019-04-15-feasible_yesno-s0` (feasible_yesno): failed: state
- `12_caltech-2019-04-22-served_share-s0` (served_share): failed: state
- `13_caltech-2019-05-01-unmet_question-s0` (unmet_question): failed: state
- `14_caltech-2019-05-08-feasible_yesno-s0` (feasible_yesno): failed: state
- `15_caltech-2019-05-15-served_share-s0` (served_share): failed: state
- `16_caltech-2019-05-22-unmet_question-s0` (unmet_question): failed: state
- `17_caltech-2019-06-03-feasible_yesno-s0` (feasible_yesno): failed: state
- `18_caltech-2019-06-10-served_share-s0` (served_share): failed: state
- `19_caltech-2019-06-15-unmet_question-s0` (unmet_question): failed: state
- `20_caltech-2019-06-20-schedule_only-s0` (schedule_only): failed: state

## Escalated: 0

none

## Every request

| nn | request | variant | outcome | form. | trace | answer | gap % | tokens |
|---|---|---|---|---|---|---|---|---|
| 01 | `caltech-2018-09-17-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | 21.61 | 0 |
| 02 | `caltech-2018-10-15-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | 30.41 | 0 |
| 03 | `caltech-2018-11-05-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | 38.67 | 0 |
| 04 | `caltech-2018-11-12-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | pass | 23.74 | 0 |
| 05 | `caltech-2018-12-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | pass | 18.16 | 0 |
| 06 | `caltech-2018-12-10-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | pass | 38.49 | 0 |
| 07 | `caltech-2019-01-15-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | 20.13 | 0 |
| 08 | `caltech-2019-01-22-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | 27.69 | 0 |
| 09 | `caltech-2019-02-20-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | pass | 23.21 | 0 |
| 10 | `caltech-2019-03-10-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | pass | 17.20 | 0 |
| 11 | `caltech-2019-04-15-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | pass | 39.53 | 0 |
| 12 | `caltech-2019-04-22-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | pass | 39.30 | 0 |
| 13 | `caltech-2019-05-01-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | pass | 34.32 | 0 |
| 14 | `caltech-2019-05-08-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | pass | 52.85 | 0 |
| 15 | `caltech-2019-05-15-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | pass | 51.50 | 0 |
| 16 | `caltech-2019-05-22-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | pass | 56.69 | 0 |
| 17 | `caltech-2019-06-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | pass | 54.61 | 0 |
| 18 | `caltech-2019-06-10-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | pass | 38.42 | 0 |
| 19 | `caltech-2019-06-15-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | pass | 21.23 | 0 |
| 20 | `caltech-2019-06-20-schedule_only-s0` | schedule_only | wrong_unflagged | - | not_checkable | not_checkable | 108.60 | 0 |
