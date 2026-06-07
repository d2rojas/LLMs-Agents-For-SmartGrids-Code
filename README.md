# LLMs and Agentic AI Systems for Smart Grids — Case-Study Code (v2)

Dedicated code repository for the four case studies in *LLMs and Agentic AI Systems
for Smart Grids: A Tutorial on Architectures and Applications* (Rojas et al.).
Companion to the paper repo `interna-LLMs-Agents-For-SmartGrids-v5`.

This repository implements the solver-grounded design rule of the paper: every
reported numerical result originates from a trusted tool (solver/simulator) and
passes explicit verification before it is reported. Each case study compares an
**LLM-only baseline** against its **solver-grounded** counterpart on identical
data and metrics.

> **Scaffold status.** This is the repository structure with per-folder reproduction
> guides. Items marked `TODO(authors)` must be filled in with the actual scripts,
> data paths, and exact run commands by the case-study owners. Nothing here invents
> results; the descriptions restate the experimental setup reported in the paper.

## Layout

| Folder | Case study | Paper section | Trusted tool | LLM-only vs solver-grounded |
|---|---|---|---|---|
| [`wind-forecasting/`](wind-forecasting/) | Wind power forecasting | §VI-A | — (no solver; LLM is the predictor) | Naive vs Advanced vs APBF prompting |
| [`ev-scheduling/`](ev-scheduling/) | EV charging scheduling | §VI-B | CVXPY LP solver | LLM-only vs EVAgent |
| [`power-flow-agent/`](power-flow-agent/) | AC power flow analysis | §VI-C | PandaPower (Newton–Raphson) | LLM-only vs PFAgent |
| [`griddebug-agent/`](griddebug-agent/) | Contingency diagnosis | §VI-D | PandaPower | LLM-only vs GridDebugAgent |

## Common setup

```bash
# Python 3.11+ recommended
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # TODO(authors): pin versions actually used
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

## Reproducibility checklist (per the paper's appendix)

- [ ] Exact model versions and decryption of run dates per case study — `TODO(authors)`.
- [ ] Random seeds (e.g., PFAgent uses `N=40` seeds; EV averages 5 runs over 20 days).
- [ ] LLM-only baseline prompts used for each head-to-head comparison.
- [ ] Evaluation harness + the exact tables (`§VI`) each script reproduces.
- [ ] License + data-use notes.

See each subfolder's `README.md` for case-specific instructions.

## Adding your code (for the case-study owners)

Each case study has the same layout:

```
<case>/
  README.md       # reproduction guide (already drafted from the paper)
  src/            # drop your scripts/notebooks here
  data/           # local data (gitignored; document the public source in README)
```

Steps:
1. Copy your existing scripts/notebooks into the matching `src/` folder.
2. Update that folder's `README.md`: fill every `TODO(authors)` (exact run
   commands, model versions, seeds, which table each script reproduces).
3. Keep raw data out of git (it is gitignored); record the public download link
   and any preprocessing in the README instead.
4. Pin the versions you actually used in the top-level `requirements.txt`.

Once code is in, we can refactor for a clean, uniform interface across the four
cases (shared config, a common `verify()` gate, consistent CLI).
