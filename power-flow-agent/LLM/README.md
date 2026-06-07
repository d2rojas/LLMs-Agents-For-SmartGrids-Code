# Power Flow Platform — Step 7+ Closed-Loop

For easy using: https://poweragent.streamlit.app/

> LLM-augmented interactive AC power flow analysis platform with closed-loop remedial control.

A Streamlit-based web application that integrates **PandaPower** numerical simulation with **LLM tool-calling** (OpenAI / Gemini) to deliver a complete power system analysis workflow: case loading, power flow solving, N-1 contingency ranking, heuristic remedial actions, and rich Plotly visualizations — all driven through a conversational chat interface.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Streamlit Frontend                          │
│  app.py (2336 L) ── UI state, chat loop, undo/redo, rendering     │
│  app_utils.py     ── helper functions for the UI layer             │
└────────────┬─────────────┬─────────────┬───────────────────────────┘
             │             │             │
     ┌───────▼──────┐ ┌───▼───────┐ ┌───▼──────────────┐
     │  LLM Engine  │ │  Solver   │ │  Visualization   │
     │  llm/        │ │  solver/  │ │  viz/            │
     └───────┬──────┘ └───┬───────┘ └──────────────────┘
             │             │
     ┌───────▼──────┐ ┌───▼───────────────────────────┐
     │  LLM APIs    │ │  PandaPower (numerical core)   │
     │  OpenAI /    │ │  IEEE test cases via           │
     │  Gemini      │ │  matpowercaseframes            │
     └──────────────┘ └───────────────────────────────┘
```

### Data Flow Pipeline

```
User input (chat)
    │
    ├─► LLM intent parsing (llm/engine.py)
    │       │
    │       ├─► Tool dispatch (llm/tools.py)
    │       │       │
    │       │       ├─► load_case      → solver/case_loader.py
    │       │       ├─► run_pf         → solver/power_flow.py
    │       │       ├─► modify_load    → solver/power_flow.py
    │       │       ├─► disconnect     → solver/power_flow.py
    │       │       ├─► reconnect      → solver/power_flow.py
    │       │       ├─► run_n1         → solver/contingency.py
    │       │       ├─► recommend      → solver/remedial.py
    │       │       └─► apply_remedial → solver/remedial.py
    │       │
    │       └─► Natural language response
    │
    ├─► Direct UI buttons (sidebar)
    │       │
    │       ├─► One-click PF / N-1 / Remedial
    │       └─► Undo / Redo stack
    │
    └─► Visualization rendering
            │
            ├─► Network topology       (viz/network_plot.py)
            ├─► Voltage heatmap        (viz/voltage_heatmap.py)
            ├─► Flow diagram + particles(viz/flow_diagram.py, flow_particles.py)
            ├─► Before/after comparison (viz/comparison.py)
            ├─► Quantitative 4-panel   (viz/comparison.py)
            ├─► N-1 ranking chart      (viz/n1.py)
            └─► Remedial ranking chart  (viz/remedial.py)
```

---

## File Inventory

### Root

| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | 2336 | Main Streamlit application — UI layout, chat loop, session state, sidebar, undo/redo, all page renderers |
| `app_utils.py` | 106 | Shared UI helper functions |
| `config.py` | 90 | Global configuration — API keys, model selection, validation thresholds; reads `.env` / `.env.local` |
| `requirements.txt` | 9 | Runtime dependencies (`streamlit`, `pandapower`, `plotly`, `openai`, `google-genai`, etc.) |
| `README.md` | — | This file |

### `models/` — Data Schemas

| File | Lines | Purpose |
|------|-------|---------|
| `schemas.py` | 131 | Pydantic models: `PowerFlowResult`, `BusVoltage`, `LineFlow`, `NetworkInfo`, `ContingencyOutcome`, `N1Report`, `RemedialAction`, `RemedialPlan`, `SessionState`, `Modification` |
| `llm_only_schema.py` | — | Schema extensions for LLM-only blueprint mode |

### `solver/` — Numerical Engine

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 59 | numba/coverage compatibility patch |
| `case_loader.py` | 175 | Load IEEE standard test cases via `matpowercaseframes`; supports case5/9/14/30/39/57/118/300 |
| `power_flow.py` | 341 | Core AC power flow wrapper — `run_power_flow()`, `modify_bus_load()`, `disconnect_line()`, `reconnect_line()`, bus ID resolution |
| `validators.py` | 121 | Post-solve validation — voltage limit check, thermal overload detection, violation annotation |
| `contingency.py` | 219 | N-1 contingency analysis — enumerate branches, simulate outages, score & rank |
| `remedial.py` | 347 | Heuristic remedial action engine — candidate generation (load shed, voltage adjust), risk scoring, action application |
| `llm_pf.py` | 628 | LLM-only power flow solver (blueprint/baseline mode) |
| `net_ops.py` | 154 | Low-level network operation utilities |
| `matpower_meta.py` | 70 | MATPOWER case metadata |
| `matpower_text.py` | 61 | MATPOWER text format parser |

### `llm/` — LLM Integration

| File | Lines | Purpose |
|------|-------|---------|
| `engine.py` | 222 | LLM call orchestrator — intent parsing, multi-turn tool calling loop, conversation history management |
| `tools.py` | 672 | Tool definitions (OpenAI function-calling format) and `ToolDispatcher` — maps LLM tool calls to solver functions |
| `prompts.py` | 47 | System prompt template for the power flow assistant |

### `viz/` — Visualization

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 25 | Package exports |
| `network_plot.py` | 624 | Network topology graph — bus nodes, branch edges, violation markers, interactive layout |
| `voltage_heatmap.py` | 98 | Bus voltage heatmap (color-coded by vm_pu) |
| `flow_diagram.py` | 618 | Power flow diagram with directional arrows and loading indicators |
| `flow_particles.py` | 306 | Animated CSS particle overlay for flow visualization |
| `comparison.py` | 841 | Before/after comparison plot + **quantitative 4-panel view** (voltage, ΔV, loading Top-15, metrics table) |
| `n1.py` | 250 | N-1 contingency ranking horizontal bar chart |
| `remedial.py` | 421 | Remedial action ranking visualization with risk reduction bars |

### `baselines/` — Evaluation Baselines

| File | Lines | Purpose |
|------|-------|---------|
| `llm_only.py` | 689 | Pure LLM power flow baseline (no numerical solver) for benchmarking |
| `prompts_baseline.py` | 68 | Prompt templates for baseline evaluation |

### `tests/` — Test Suite

| File | Purpose |
|------|---------|
| `test_solver.py` | Power flow solver unit tests |
| `test_remedial.py` | Remedial action generation & application tests |
| `test_n1.py` | N-1 contingency analysis tests |
| `test_viz.py` | Visualization rendering tests |
| `test_llm.py` | LLM engine integration tests |
| `test_tools_apply.py` | Tool dispatcher application tests |
| `test_app_smoke.py` | Streamlit app smoke tests |
| `test_flow_particles.py` | Flow particle animation tests |
| `test_baseline.py` | Baseline evaluation tests |
| `test_llm_only_blueprint.py` | LLM-only blueprint mode tests |

### `scripts/` & `data/`

| Path | Purpose |
|------|---------|
| `scripts/fetch_matpower_cases.py` | Download/prepare MATPOWER case data |
| `data/matpower/` | Cached MATPOWER case files |
| `benchmarks/` | Benchmark results |
| `docs/` | Additional documentation (e.g., `quantitative-comparison.md`) |

---

## Core Design Decisions

### 1. Single-LLM + Tool Calling (No Agent Framework)

The platform deliberately avoids LangChain / LangGraph / multi-agent patterns. Instead:
- One LLM instance handles intent parsing via OpenAI-compatible function calling
- `ToolDispatcher` maps tool names to solver functions with parameter validation
- Multi-turn tool calling is handled by a simple loop in `engine.py`
- This keeps the stack minimal, debuggable, and latency-predictable

### 2. Bus ID Resolution

MATPOWER cases use 1-based bus numbering; PandaPower uses 0-based DataFrame indices. Three resolution strategies are chained in `_resolve_bus_index()`:
1. Match `bus.name` column as string
2. Parse `bus.name` as integer and match
3. Match via `display_id = index + 1` convention
4. Fall back to raw index

This is replicated consistently across `power_flow.py`, `remedial.py`, and `contingency.py`.

### 3. Undo / Redo via Deep Copy Snapshots

`app.py` maintains an undo stack of `(label, net_deepcopy)` tuples. Snapshots are pushed **before** any in-place network modification. On failure, `_undo_last()` restores the previous state. This provides full reversibility for load modifications, line disconnections, and remedial actions.

### 4. Risk-Based Remedial Scoring

`remedial.py` uses a weighted risk score to rank candidate actions:
- `violation_count × 10,000` — penalize number of violations
- `undervoltage_deviation × 100,000` — heavy penalty for low voltage
- `overvoltage_deviation × 50,000` — moderate penalty for high voltage
- `overload_deviation × 1,000` — penalty for thermal overload
- `non_converged = 10⁹` — effectively infinite penalty

Candidate actions (load shedding 5/10/20%, generator voltage ±0.01/0.02 p.u.) are generated for the top-3 worst violations and their network neighbors, then scored by running full AC power flow simulations.

### 5. Quantitative Comparison View

A 2×2 Plotly subplot panel provides before/after remedial action comparison:
- **Panel 1** (top-left): Voltage magnitude scatter with violation shading bands
- **Panel 2** (top-right): ΔV change bar chart per bus
- **Panel 3** (bottom-left): Top-15 line loading grouped bars
- **Panel 4** (bottom-right): Key metrics table (generation, load, losses, violations)

Legend groups link traces across panels so toggling "Before"/"After" in the legend affects all subplots simultaneously.

### 6. Dual LLM Provider Support

The platform supports both **OpenAI** and **Google Gemini** as LLM backends:
- Provider and model are selectable from the sidebar
- API keys are loaded from environment variables or `.env` files
- The same tool-calling protocol works with both providers

---

## Quick Start

### Prerequisites

- Python 3.10+
- PandaPower (installed as dependency of `matpowercaseframes`)

### Installation

```bash
# Clone the repository
cd power-flow-platform_step7plus

# Install dependencies
pip install -r requirements.txt

# Set up API keys (optional — needed for LLM chat features)
cp .env.local.example .env.local
# Edit .env.local with your OPENAI_API_KEY and/or GEMINI_API_KEY
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` | Gemini model name |
| `V_MIN` | `0.95` | Minimum voltage threshold (p.u.) |
| `V_MAX` | `1.05` | Maximum voltage threshold (p.u.) |
| `MAX_LOADING` | `100` | Maximum branch loading (%) |

### Running

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Usage Guide

### 1. Load a Test Case

- **Sidebar**: Select a case from the dropdown (case5, case9, case14, case30, case39, case57, case118, case300)
- **Chat**: Type "load case14" or "加载 case14"

### 2. Run Power Flow

- **Sidebar**: Click "Run Power Flow" button
- **Chat**: Type "run power flow" or "运行潮流计算"
- Results show bus voltages, line flows, violations, and network topology

### 3. Modify the Network

- **Chat**: "Set load at bus 3 to 50 MW" / "修改母线3负荷为50MW"
- **Chat**: "Disconnect line between bus 1 and bus 2" / "断开母线1到母线2的线路"
- **Chat**: "Reconnect line between bus 1 and bus 2"
- Each modification auto-runs power flow and shows updated results

### 4. N-1 Contingency Analysis

- **Sidebar**: Click "N-1 Analysis" button
- **Chat**: Type "run N-1 analysis" or "N-1分析"
- Shows ranked list of critical contingencies with severity scores

### 5. Remedial Actions

- **Sidebar**: Click "Remedial" button after violations are detected
- Shows ranked candidate actions (load shedding, voltage adjustment)
- Click "Apply" on any action to execute it on the network
- Before/after comparison and quantitative 4-panel view are displayed

### 6. Undo / Redo

- **Sidebar**: Undo / Redo buttons to navigate through modification history
- Full network state is restored on each undo/redo step

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test modules
pytest tests/test_solver.py -v
pytest tests/test_remedial.py -v
pytest tests/test_viz.py -v
```

---

## Project Statistics

- **Total Python source**: ~11,000 lines across 43 files
- **Core modules**: 5 packages (`solver`, `llm`, `viz`, `models`, `baselines`)
- **Test coverage**: 10 test modules with 57+ test cases
- **Supported cases**: IEEE 5/9/14/30/39/57/118/300 bus systems
- **Visualization types**: 7 distinct Plotly chart types

---

## Known Limitations & Future Work

1. **Scaling**: Deep-copy undo snapshots become memory-intensive for large networks (300+ buses)
2. **Remedial search**: Heuristic candidate generation covers load shedding and voltage control only; topology switching (line switching, bus splitting) is not yet supported
3. **LLM dependency**: Chat-based interaction requires a valid API key; all solver functionality works without LLM via sidebar buttons
4. **Single-session**: No persistent storage; all state is in Streamlit session state
5. **Contingency scoring**: N-1 scoring uses hardcoded magic numbers; could benefit from configurable weight profiles

---

## License

Internal / Research use.
