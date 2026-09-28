# llm_only_cot on caltech, 2026-09-28, gpt-4o-mini

Built from `ev_matrix_openrouter_openai_gpt-4o-mini_rescored` by `evaluation/postprocess.py`. No model was called to write this report.

## Outcome

| solved | escalated | wrong, unflagged | run error |
|---|---|---|---|
| 0.0 % (0/20) | 0.0 % (0/20) | 100.0 % (20/20) | 0 |

The three outcomes are exclusive and sum to the request count.

## Formulation, traceability, cost

| formulation exact (days) | traceable answers | tokens | est. cost |
|---|---|---|---|
| 5.26 % | - % | 162,873 | $0.0708 |

## Wrong and unflagged: 20

- `01_caltech-2018-09-17-unmet_question-s0` (unmet_question): failed: state, answer
- `02_caltech-2018-10-15-served_share-s0` (served_share): failed: state, answer
- `03_caltech-2018-11-05-unmet_question-s0` (unmet_question): failed: state, answer
- `04_caltech-2018-11-12-feasible_yesno-s0` (feasible_yesno): failed: state, answer
- `05_caltech-2018-12-03-feasible_yesno-s0` (feasible_yesno): failed: state, answer
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
| 01 | `caltech-2018-09-17-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -100.00 | 12730 |
| 02 | `caltech-2018-10-15-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 379.49 | 11964 |
| 03 | `caltech-2018-11-05-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 359.73 | 10797 |
| 04 | `caltech-2018-11-12-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | fail | 278.39 | 8858 |
| 05 | `caltech-2018-12-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | fail | 230.71 | 7144 |
| 06 | `caltech-2018-12-10-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 203.75 | 7885 |
| 07 | `caltech-2019-01-15-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 210.41 | 8837 |
| 08 | `caltech-2019-01-22-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 249.06 | 7296 |
| 09 | `caltech-2019-02-20-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | pass | 184.78 | 8374 |
| 10 | `caltech-2019-03-10-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 65.78 | 3797 |
| 11 | `caltech-2019-04-15-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | fail | 829.50 | 7108 |
| 12 | `caltech-2019-04-22-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 448.60 | 7305 |
| 13 | `caltech-2019-05-01-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 419.33 | 7939 |
| 14 | `caltech-2019-05-08-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | fail | 363.77 | 8277 |
| 15 | `caltech-2019-05-15-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 463.17 | 10096 |
| 16 | `caltech-2019-05-22-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 683.38 | 7671 |
| 17 | `caltech-2019-06-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | fail | 303.75 | 8721 |
| 18 | `caltech-2019-06-10-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 145.28 | 7583 |
| 19 | `caltech-2019-06-15-unmet_question-s0` | unmet_question | wrong_unflagged | exact | not_checkable | fail | 122.64 | 4503 |
| 20 | `caltech-2019-06-20-schedule_only-s0` | schedule_only | wrong_unflagged | wrong_field | not_checkable | not_checkable | 452.07 | 5988 |
