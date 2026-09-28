# ui/

The FastAPI backend (`app.py`) and Next.js frontend (`frontend/`) of the original GridDebugAgent
project, with its natural-language scenario generator and code sandbox. It predates the layout of
the case study and imports the classes of the original `backend/` package (`BaselineAgent`,
`IterativeDebuggerAgent`), which the six methods under `methods/` replaced; it is kept as it was
and is not wired to them. It is not part of the evaluation and nothing in `results/` comes from it.
