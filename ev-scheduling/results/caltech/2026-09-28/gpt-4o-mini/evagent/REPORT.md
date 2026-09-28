# evagent on caltech, 2026-09-28, gpt-4o-mini

Built from `ev_e7_evagent` by `evaluation/postprocess.py`. No model was called to write this report.

## Outcome

| solved | escalated | wrong, unflagged | run error |
|---|---|---|---|
| 0.0 % (0/20) | 100.0 % (20/20) | 0.0 % (0/20) | 0 |

The three outcomes are exclusive and sum to the request count.

## Formulation, traceability, cost

| formulation exact (days) | traceable answers | tokens | est. cost |
|---|---|---|---|
| 0.00 % | 95.00 % | 338,793 | $0.0752 |

## Wrong and unflagged: 0

none

## Escalated: 20

- `01_caltech-2018-09-17-unmet_question-s0` (unmet_question): the gate failed and the answer declares the failure
- `02_caltech-2018-10-15-served_share-s0` (served_share): the gate failed and the answer declares the failure
- `03_caltech-2018-11-05-unmet_question-s0` (unmet_question): the gate failed and the answer declares the failure
- `04_caltech-2018-11-12-feasible_yesno-s0` (feasible_yesno): the gate failed and the answer declares the failure
- `05_caltech-2018-12-03-feasible_yesno-s0` (feasible_yesno): the gate failed and the answer declares the failure
- `06_caltech-2018-12-10-served_share-s0` (served_share): the gate failed and the answer declares the failure
- `07_caltech-2019-01-15-served_share-s0` (served_share): the gate failed and the answer declares the failure
- `08_caltech-2019-01-22-unmet_question-s0` (unmet_question): the gate failed and the answer declares the failure
- `09_caltech-2019-02-20-feasible_yesno-s0` (feasible_yesno): the gate failed and the answer declares the failure
- `10_caltech-2019-03-10-unmet_question-s0` (unmet_question): the gate failed and the answer declares the failure
- `11_caltech-2019-04-15-feasible_yesno-s0` (feasible_yesno): the gate failed and the answer declares the failure
- `12_caltech-2019-04-22-served_share-s0` (served_share): the gate failed and the answer declares the failure
- `13_caltech-2019-05-01-unmet_question-s0` (unmet_question): the gate failed and the answer declares the failure
- `14_caltech-2019-05-08-feasible_yesno-s0` (feasible_yesno): the gate failed and the answer declares the failure
- `15_caltech-2019-05-15-served_share-s0` (served_share): the gate failed and the answer declares the failure
- `16_caltech-2019-05-22-unmet_question-s0` (unmet_question): the gate failed and the answer declares the failure
- `17_caltech-2019-06-03-feasible_yesno-s0` (feasible_yesno): the gate failed and the answer declares the failure
- `18_caltech-2019-06-10-served_share-s0` (served_share): the gate failed and the answer declares the failure
- `19_caltech-2019-06-15-unmet_question-s0` (unmet_question): the gate failed and the answer declares the failure
- `20_caltech-2019-06-20-schedule_only-s0` (schedule_only): the gate failed and the answer declares the failure

## Every request

| nn | request | variant | outcome | form. | trace | answer | gap % | tokens |
|---|---|---|---|---|---|---|---|---|
| 01 | `caltech-2018-09-17-unmet_question-s0` | unmet_question | escalated | wrong_field | pass | fail | -100.00 | 26992 |
| 02 | `caltech-2018-10-15-served_share-s0` | served_share | escalated | wrong_field | pass | fail | -100.00 | 23645 |
| 03 | `caltech-2018-11-05-unmet_question-s0` | unmet_question | escalated | wrong_field | pass | fail | -100.00 | 22196 |
| 04 | `caltech-2018-11-12-feasible_yesno-s0` | feasible_yesno | escalated | wrong_field | pass | pass | -100.00 | 18755 |
| 05 | `caltech-2018-12-03-feasible_yesno-s0` | feasible_yesno | escalated | wrong_field | pass | pass | -100.00 | 15600 |
| 06 | `caltech-2018-12-10-served_share-s0` | served_share | escalated | wrong_field | pass | fail | -100.00 | 17085 |
| 07 | `caltech-2019-01-15-served_share-s0` | served_share | escalated | wrong_field | fail | fail | -100.00 | 18387 |
| 08 | `caltech-2019-01-22-unmet_question-s0` | unmet_question | escalated | wrong_field | pass | fail | -100.00 | 15862 |
| 09 | `caltech-2019-02-20-feasible_yesno-s0` | feasible_yesno | escalated | wrong_field | pass | pass | -100.00 | 17800 |
| 10 | `caltech-2019-03-10-unmet_question-s0` | unmet_question | escalated | wrong_field | pass | fail | -100.00 | 8840 |
| 11 | `caltech-2019-04-15-feasible_yesno-s0` | feasible_yesno | escalated | wrong_field | pass | pass | -100.00 | 14432 |
| 12 | `caltech-2019-04-22-served_share-s0` | served_share | escalated | wrong_field | pass | fail | -100.00 | 16064 |
| 13 | `caltech-2019-05-01-unmet_question-s0` | unmet_question | escalated | wrong_field | pass | fail | -100.00 | 16770 |
| 14 | `caltech-2019-05-08-feasible_yesno-s0` | feasible_yesno | escalated | wrong_field | pass | pass | -100.00 | 17431 |
| 15 | `caltech-2019-05-15-served_share-s0` | served_share | escalated | wrong_field | pass | fail | -100.00 | 16713 |
| 16 | `caltech-2019-05-22-unmet_question-s0` | unmet_question | escalated | wrong_field | pass | fail | -100.00 | 16595 |
| 17 | `caltech-2019-06-03-feasible_yesno-s0` | feasible_yesno | escalated | wrong_field | pass | pass | -100.00 | 15632 |
| 18 | `caltech-2019-06-10-served_share-s0` | served_share | escalated | wrong_field | pass | fail | -100.00 | 16475 |
| 19 | `caltech-2019-06-15-unmet_question-s0` | unmet_question | escalated | wrong_field | pass | fail | -100.00 | 9983 |
| 20 | `caltech-2019-06-20-schedule_only-s0` | schedule_only | escalated | wrong_field | pass | not_checkable | -100.00 | 13536 |
