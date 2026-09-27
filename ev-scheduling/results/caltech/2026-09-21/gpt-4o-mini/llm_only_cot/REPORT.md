# llm_only_cot on caltech, 2026-09-21, gpt-4o-mini

Built from `ev_matrix_openrouter_openai_gpt-4o-mini_v2` by `evaluation/postprocess.py`. No model was called to write this report.

## Outcome

| solved | escalated | wrong, unflagged | run error |
|---|---|---|---|
| 0.0 % (0/20) | 0.0 % (0/20) | 100.0 % (20/20) | 0 |

The three outcomes are exclusive and sum to the request count.

## Formulation, traceability, cost

| formulation exact (days) | traceable answers | tokens | est. cost |
|---|---|---|---|
| - % | - % | 378,157 | $0.2042 |

## Wrong and unflagged: 20

- `01_caltech-2018-09-17-unmet_question-s0` (unmet_question): failed: state, answer
- `02_caltech-2018-10-15-served_share-s0` (served_share): failed: state, answer
- `03_caltech-2018-11-05-unmet_question-s0` (unmet_question): failed: state, answer
- `04_caltech-2018-11-12-feasible_yesno-s0` (feasible_yesno): failed: state, answer
- `05_caltech-2018-12-03-feasible_yesno-s0` (feasible_yesno): failed: state, answer
- `06_caltech-2018-12-10-served_share-s0` (served_share): failed: state, answer
- `07_caltech-2019-01-15-served_share-s0` (served_share): failed: state, answer
- `08_caltech-2019-01-22-unmet_question-s0` (unmet_question): failed: state, answer
- `09_caltech-2019-02-20-feasible_yesno-s0` (feasible_yesno): failed: state, answer
- `10_caltech-2019-03-10-unmet_question-s0` (unmet_question): failed: state, answer
- `11_caltech-2019-04-15-feasible_yesno-s0` (feasible_yesno): failed: state, answer
- `12_caltech-2019-04-22-served_share-s0` (served_share): failed: state, answer
- `13_caltech-2019-05-01-unmet_question-s0` (unmet_question): failed: state, answer
- `14_caltech-2019-05-08-feasible_yesno-s0` (feasible_yesno): failed: state, answer
- `15_caltech-2019-05-15-served_share-s0` (served_share): failed: state, answer
- `16_caltech-2019-05-22-unmet_question-s0` (unmet_question): failed: state, answer
- `17_caltech-2019-06-03-feasible_yesno-s0` (feasible_yesno): failed: state, answer
- `18_caltech-2019-06-10-served_share-s0` (served_share): failed: state, answer
- `19_caltech-2019-06-15-unmet_question-s0` (unmet_question): failed: state, answer
- `20_caltech-2019-06-20-schedule_only-s0` (schedule_only): failed: state

## Escalated: 0

none

## Every request

| nn | request | variant | outcome | form. | trace | answer | gap % | tokens |
|---|---|---|---|---|---|---|---|---|
| 01 | `caltech-2018-09-17-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -98.02 | 20457 |
| 02 | `caltech-2018-10-15-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | -100.00 | 19932 |
| 03 | `caltech-2018-11-05-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -100.00 | 19718 |
| 04 | `caltech-2018-11-12-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | 43.15 | 19219 |
| 05 | `caltech-2018-12-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | -99.92 | 18722 |
| 06 | `caltech-2018-12-10-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | 201.45 | 18924 |
| 07 | `caltech-2019-01-15-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | -100.00 | 19128 |
| 08 | `caltech-2019-01-22-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -100.00 | 18738 |
| 09 | `caltech-2019-02-20-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | -99.92 | 19029 |
| 10 | `caltech-2019-03-10-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -96.65 | 17698 |
| 11 | `caltech-2019-04-15-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | -100.00 | 18554 |
| 12 | `caltech-2019-04-22-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | -100.00 | 18758 |
| 13 | `caltech-2019-05-01-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -99.84 | 18872 |
| 14 | `caltech-2019-05-08-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | -95.74 | 18976 |
| 15 | `caltech-2019-05-15-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | 220.22 | 18863 |
| 16 | `caltech-2019-05-22-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | 1266.40 | 18855 |
| 17 | `caltech-2019-06-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | -100.00 | 18731 |
| 18 | `caltech-2019-06-10-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | -98.69 | 18849 |
| 19 | `caltech-2019-06-15-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -100.00 | 17879 |
| 20 | `caltech-2019-06-20-schedule_only-s0` | schedule_only | wrong_unflagged | - | not_checkable | not_checkable | 185.93 | 18255 |
