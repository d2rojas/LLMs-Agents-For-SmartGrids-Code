# Extraction probe

`openrouter:openai/gpt-5.6-sol` on 10 of 10 frozen days, 382 cars. Extraction prompt `c6d0f98682f0d0ecab57`. No tool call, no answer turn, no gate: this is the reading step alone.

- cars read exactly: **380/382** (99.5 %)
- days with every car exact: **8/10**
- clock errors: **2**, of which **0** are exactly thirty minutes early

| field | errors |
|---|---|
| `departure_idx` | 2 |

| clock phrase in that car's sentence | errors |
|---|---|
| digits | 2 |

| offset | errors |
|---|---|
| -60 min | 2 |
