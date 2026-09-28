# llm_only_structured on caltech, 2026-09-28, gpt-4o-mini

Built from `ev_matrix_openrouter_openai_gpt-4o-mini_rescored` by `evaluation/postprocess.py`. No model was called to write this report.

## Outcome

| solved | escalated | wrong, unflagged | run error |
|---|---|---|---|
| 0.0 % (0/20) | 0.0 % (0/20) | 100.0 % (20/20) | 0 |

The three outcomes are exclusive and sum to the request count.

## Formulation, traceability, cost

| formulation exact (days) | traceable answers | tokens | est. cost |
|---|---|---|---|
| 0.00 % | - % | 126,140 | $0.0512 |

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
- `11_caltech-2019-04-15-feasible_yesno-s0` (feasible_yesno): failed: state
- `12_caltech-2019-04-22-served_share-s0` (served_share): failed: state, answer
- `13_caltech-2019-05-01-unmet_question-s0` (unmet_question): failed: state, answer
- `14_caltech-2019-05-08-feasible_yesno-s0` (feasible_yesno): failed: state, answer
- `15_caltech-2019-05-15-served_share-s0` (served_share): failed: state, answer
- `16_caltech-2019-05-22-unmet_question-s0` (unmet_question): failed: state, answer
- `17_caltech-2019-06-03-feasible_yesno-s0` (feasible_yesno): failed: state
- `18_caltech-2019-06-10-served_share-s0` (served_share): failed: state, answer
- `19_caltech-2019-06-15-unmet_question-s0` (unmet_question): failed: state, answer
- `20_caltech-2019-06-20-schedule_only-s0` (schedule_only): failed: state

## Escalated: 0

none

## Every request

| nn | request | variant | outcome | form. | trace | answer | gap % | tokens |
|---|---|---|---|---|---|---|---|---|
| 01 | `caltech-2018-09-17-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 428.29 | 10338 |
| 02 | `caltech-2018-10-15-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 457.42 | 8872 |
| 03 | `caltech-2018-11-05-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 365.00 | 8173 |
| 04 | `caltech-2018-11-12-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | fail | 278.82 | 6614 |
| 05 | `caltech-2018-12-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | fail | 227.79 | 5289 |
| 06 | `caltech-2018-12-10-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 302.30 | 5922 |
| 07 | `caltech-2019-01-15-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 150.87 | 6547 |
| 08 | `caltech-2019-01-22-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 167.75 | 5735 |
| 09 | `caltech-2019-02-20-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | pass | 198.37 | 6286 |
| 10 | `caltech-2019-03-10-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 119.25 | 2271 |
| 11 | `caltech-2019-04-15-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | pass | 349.58 | 4933 |
| 12 | `caltech-2019-04-22-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 407.80 | 8353 |
| 13 | `caltech-2019-05-01-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 411.23 | 5786 |
| 14 | `caltech-2019-05-08-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | fail | 618.03 | 8984 |
| 15 | `caltech-2019-05-15-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 405.25 | 8145 |
| 16 | `caltech-2019-05-22-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 577.43 | 5677 |
| 17 | `caltech-2019-06-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | wrong_field | not_checkable | pass | 400.53 | 5281 |
| 18 | `caltech-2019-06-10-served_share-s0` | served_share | wrong_unflagged | wrong_field | not_checkable | fail | 376.14 | 5701 |
| 19 | `caltech-2019-06-15-unmet_question-s0` | unmet_question | wrong_unflagged | wrong_field | not_checkable | fail | 112.68 | 2798 |
| 20 | `caltech-2019-06-20-schedule_only-s0` | schedule_only | wrong_unflagged | wrong_field | not_checkable | not_checkable | 747.89 | 4435 |
