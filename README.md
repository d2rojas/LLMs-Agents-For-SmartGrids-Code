# LLMs and Agentic AI Systems for Smart Grids — Case-Study Code

Dedicated code repository for the four case studies in *LLMs and Agentic AI Systems
for Smart Grids: A Tutorial on Architectures and Applications* (Rojas et al.).


This repository implements the solver-grounded design rule of the paper: every
reported numerical result originates from a trusted tool (solver/simulator) and
passes explicit verification before it is reported. Each case study compares an
**LLM-only baseline** against its **solver-grounded** counterpart on identical
data and metrics.

Each case study is a complete, runnable implementation with its own README,
dependencies, and tests. Per-case install and run instructions live in each
subfolder.

## Layout

| Folder | Case study | Paper section | Trusted tool | LLM-only vs solver-grounded |
|---|---|---|---|---|
| [`wind-forecasting/`](wind-forecasting/) | Wind power forecasting | §VI-A | — (no solver; LLM is the predictor) | Naive vs Advanced vs APBF prompting |
| [`ev-scheduling/`](ev-scheduling/) | EV charging scheduling | §VI-B | CVXPY LP solver | LLM-only vs EVAgent |
| [`power-flow-agent/`](power-flow-agent/) | AC power flow analysis | §VI-C | PandaPower (Newton–Raphson) | LLM-only vs PFAgent |
| [`griddebug-agent/`](griddebug-agent/) | Contingency diagnosis | §VI-D | PandaPower | LLM-only vs GridDebugAgent |

## Common setup

Each case study has its own pinned `requirements.txt`; install per case rather than
globally:

```bash
# Python 3.11+ recommended
cd <case-folder>            # e.g. power-flow-agent/LLM, ev-scheduling, ...
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Set API keys for the LLM providers used in the paper (all model versions are
real as of 2026):

```bash
export OPENAI_API_KEY=...      # GPT-4o, GPT-5.4, GPT-5.5
export ANTHROPIC_API_KEY=...   # Claude Sonnet 4.6, Claude Opus 4.7
export GEMINI_API_KEY=...      # Gemini 3 Flash
```

## Datasets and solvers (public)

- **SDWPF** wind dataset — Zhou et al., *Scientific Data* 2024 (DOI 10.1038/s41597-024-03427-5).
- **Caltech ACN-Data** (JPL site) — Lee et al., ACM e-Energy 2019.
- **MATPOWER / PandaPower IEEE 14/30/57/118** standard test cases.
- Solvers: **CVXPY** (Diamond & Boyd 2016), **PandaPower** (Thurner et al. 2018).

## Reproducibility

Each case study is self-contained: its own `README`, a pinned `requirements.txt`,
the LLM-only baseline prompts used in the head-to-head comparisons, and the harness
that regenerates its table in the paper (§VI). Raw data and large artifacts are
gitignored; each case README documents the public data source. Random seeds and
decoding temperatures are fixed to the values reported in each result table. See each
subfolder's `README.md` for case-specific install and run instructions.

## Tests

The `power-flow-agent` and `ev-scheduling` cases include test suites for their
solver and verification paths; these run without API keys. For example:
```bash
cd power-flow-agent/LLM && pip install -r requirements.txt pytest && pytest
cd ev-scheduling      && pip install -r requirements.txt pytest && pytest
```
