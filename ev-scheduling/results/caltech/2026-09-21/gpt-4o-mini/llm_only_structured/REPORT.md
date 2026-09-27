# llm_only_structured on caltech, 2026-09-21, gpt-4o-mini

Built from `ev_matrix_openrouter_openai_gpt-4o-mini_v2` by `evaluation/postprocess.py`. No model was called to write this report.

## Outcome

| solved | escalated | wrong, unflagged | run error |
|---|---|---|---|
| 0.0 % (0/20) | 0.0 % (0/20) | 100.0 % (20/20) | 0 |

The three outcomes are exclusive and sum to the request count.

## Formulation, traceability, cost

| formulation exact (days) | traceable answers | tokens | est. cost |
|---|---|---|---|
| - % | - % | 373,337 | $0.2035 |

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
| 01 | `caltech-2018-09-17-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | 534.36 | 20216 |
| 02 | `caltech-2018-10-15-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | -100.00 | 19691 |
| 03 | `caltech-2018-11-05-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -100.00 | 19477 |
| 04 | `caltech-2018-11-12-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | -100.00 | 18978 |
| 05 | `caltech-2018-12-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | -100.00 | 18481 |
| 06 | `caltech-2018-12-10-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | -100.00 | 18683 |
| 07 | `caltech-2019-01-15-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | -100.00 | 18887 |
| 08 | `caltech-2019-01-22-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -100.00 | 18497 |
| 09 | `caltech-2019-02-20-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | -100.00 | 18788 |
| 10 | `caltech-2019-03-10-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -100.00 | 17457 |
| 11 | `caltech-2019-04-15-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | -100.00 | 18313 |
| 12 | `caltech-2019-04-22-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | -100.00 | 18517 |
| 13 | `caltech-2019-05-01-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -100.00 | 18631 |
| 14 | `caltech-2019-05-08-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | -100.00 | 18735 |
| 15 | `caltech-2019-05-15-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | -100.00 | 18622 |
| 16 | `caltech-2019-05-22-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -100.00 | 18614 |
| 17 | `caltech-2019-06-03-feasible_yesno-s0` | feasible_yesno | wrong_unflagged | - | not_checkable | fail | -100.00 | 18490 |
| 18 | `caltech-2019-06-10-served_share-s0` | served_share | wrong_unflagged | - | not_checkable | fail | -100.00 | 18608 |
| 19 | `caltech-2019-06-15-unmet_question-s0` | unmet_question | wrong_unflagged | - | not_checkable | fail | -100.00 | 17638 |
| 20 | `caltech-2019-06-20-schedule_only-s0` | schedule_only | wrong_unflagged | - | not_checkable | not_checkable | -100.00 | 18014 |
