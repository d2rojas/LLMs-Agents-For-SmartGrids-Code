# rule_based on caltech, 2026-09-28, no-llm

Built from `ev_matrix_openrouter_openai_gpt-4o-mini_rescored` by `evaluation/postprocess.py`. No model was called to write this report.

## Outcome

| solved | escalated | wrong, unflagged | run error |
|---|---|---|---|
| 90.0 % (18/20) | 0.0 % (0/20) | 10.0 % (2/20) | 0 |

The three outcomes are exclusive and sum to the request count.

## Formulation, traceability, cost

| formulation exact (days) | traceable answers | tokens | est. cost |
|---|---|---|---|
| 100.00 % | - % | 0 | $0.0000 |

## Wrong and unflagged: 2

- `03_caltech-2018-11-05-unmet_question-s0` (unmet_question): failed: answer
- `08_caltech-2019-01-22-unmet_question-s0` (unmet_question): failed: answer

## Escalated: 0

none

## Every request

| nn | request | variant | outcome | form. | trace | answer | gap % | tokens |
|---|---|---|---|---|---|---|---|---|
| 01 | `caltech-2018-09-17-unmet_question-s0` | unmet_question | solved | exact | not_checkable | pass | 0.00 | 0 |
| 02 | `caltech-2018-10-15-served_share-s0` | served_share | solved | exact | not_checkable | pass | -0.00 | 0 |
| 03 | `caltech-2018-11-05-unmet_question-s0` | unmet_question | wrong_unflagged | exact | not_checkable | fail | -0.00 | 0 |
| 04 | `caltech-2018-11-12-feasible_yesno-s0` | feasible_yesno | solved | exact | not_checkable | pass | -0.01 | 0 |
| 05 | `caltech-2018-12-03-feasible_yesno-s0` | feasible_yesno | solved | exact | not_checkable | pass | -0.00 | 0 |
| 06 | `caltech-2018-12-10-served_share-s0` | served_share | solved | exact | not_checkable | pass | -0.00 | 0 |
| 07 | `caltech-2019-01-15-served_share-s0` | served_share | solved | exact | not_checkable | pass | 0.00 | 0 |
| 08 | `caltech-2019-01-22-unmet_question-s0` | unmet_question | wrong_unflagged | exact | not_checkable | fail | -0.00 | 0 |
| 09 | `caltech-2019-02-20-feasible_yesno-s0` | feasible_yesno | solved | exact | not_checkable | pass | 0.00 | 0 |
| 10 | `caltech-2019-03-10-unmet_question-s0` | unmet_question | solved | exact | not_checkable | pass | -0.01 | 0 |
| 11 | `caltech-2019-04-15-feasible_yesno-s0` | feasible_yesno | solved | exact | not_checkable | pass | -0.00 | 0 |
| 12 | `caltech-2019-04-22-served_share-s0` | served_share | solved | exact | not_checkable | pass | -0.01 | 0 |
| 13 | `caltech-2019-05-01-unmet_question-s0` | unmet_question | solved | exact | not_checkable | pass | 0.01 | 0 |
| 14 | `caltech-2019-05-08-feasible_yesno-s0` | feasible_yesno | solved | exact | not_checkable | pass | 0.00 | 0 |
| 15 | `caltech-2019-05-15-served_share-s0` | served_share | solved | exact | not_checkable | pass | -0.00 | 0 |
| 16 | `caltech-2019-05-22-unmet_question-s0` | unmet_question | solved | exact | not_checkable | pass | -0.02 | 0 |
| 17 | `caltech-2019-06-03-feasible_yesno-s0` | feasible_yesno | solved | exact | not_checkable | pass | 0.01 | 0 |
| 18 | `caltech-2019-06-10-served_share-s0` | served_share | solved | exact | not_checkable | pass | -0.00 | 0 |
| 19 | `caltech-2019-06-15-unmet_question-s0` | unmet_question | solved | exact | not_checkable | pass | -0.00 | 0 |
| 20 | `caltech-2019-06-20-schedule_only-s0` | schedule_only | solved | exact | not_checkable | not_checkable | 0.00 | 0 |
