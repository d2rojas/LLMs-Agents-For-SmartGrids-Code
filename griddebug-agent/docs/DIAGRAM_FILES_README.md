# GridDebugAgent Diagram Files - Summary

## Overview
This document describes the architecture diagram files created for the GridDebugAgent project based on the students' actual implementation.

## Files Created

### 1. `architecture_diagram_prompt.txt`
**Purpose:** Comprehensive prompt for generating architecture diagrams

**Contents:**
- Complete system overview
- Detailed breakdown of all 6 major components
- Full listing of all 23 tools across 4 categories
- Memory and state management details
- Data flow description
- Implementation specifications (GPT-4o, temp=0.3, etc.)

**Use cases:**
- Reference for understanding the complete architecture
- Input prompt for AI diagram generation tools
- Documentation for future modifications
- Specification for custom diagram tools

---

### 2. `griddebug_architecture.mmd`
**Purpose:** Mermaid diagram source file

**Format:** Mermaid markdown diagram

**Features:**
- Visual hierarchy with subgraphs for each component
- Color-coded nodes by component type:
  - Blue: Input layer
  - Orange: Preprocessing
  - Purple: Agent core (ReAct loop)
  - Green: Tool categories
  - Red/Pink: Memory and state
  - Teal: Output layer
- Solid arrows: main data flow
- Dashed arrows: memory/state interactions
- Icons for visual clarity (📥📊🤖🛠️💾📤)

**How to use:**
- Render online: https://mermaid.live/ (paste content)
- VS Code: Install "Markdown Preview Mermaid Support" extension
- Command line: `mmdc -i griddebug_architecture.mmd -o diagram.png`
- Documentation sites: GitHub, GitLab, Notion all support Mermaid

**Advantages:**
- Easy to edit (plain text)
- Version control friendly
- Quick iteration
- Multiple export formats (PNG, SVG, PDF)

---

### 3. `griddebug_architecture.tex`
**Purpose:** Publication-quality TikZ diagram for LaTeX paper

**Format:** LaTeX figure environment with TikZ/PGF

**Features:**
- IEEE paper compatible (figure*)
- Professional styling with consistent colors
- Compact layout optimized for two-column format
- Comprehensive caption with full system description
- Label: `\label{fig:griddebug_architecture}`
- Shows all 23 tools with categories
- ReAct loop highlighted with rounded corners
- Memory interactions shown with dashed lines

**Required LaTeX packages:**
```latex
\usepackage{tikz}
\usetikzlibrary{positioning, shapes, arrows, calc}
```

**How to use:**
1. Add required packages to your LaTeX preamble
2. Insert the file content where you want the figure:
   ```latex
   \input{griddebug_architecture.tex}
   ```
   Or copy-paste the entire figure environment into your .tex file

3. Reference in text:
   ```latex
   Figure~\ref{fig:griddebug_architecture} shows the GridDebugAgent architecture...
   ```

**Customization tips:**
- Adjust `node distance` to change spacing
- Modify colors in style definitions (e.g., `fill=blue!10`)
- Change font sizes: `\small`, `\footnotesize`, `\scriptsize`
- Add/remove tools as needed in the tool boxes

---

## Architecture Summary

### Component Breakdown

| Component | Count | Description |
|-----------|-------|-------------|
| **Input Layer** | 3 elements | User query, pandapower network, network name |
| **Preprocessing** | 3 modules | Evidence collector, rule engine, context builder |
| **Agent Core** | 4 elements | GPT-4o, function calling, tool executor, ReAct loop |
| **Tool Categories** | 4 categories, 23 tools | Query (9), Simulation (7), Diagnostic (4), Grid Actions (4) |
| **Memory** | 3 types | Network snapshots, conversation history, tool call logs |
| **Output** | 2 types | Diagnostic report, metadata |

### Tool Categories Detail

**Query Tools (9):**
1. get_network_summary
2. get_bus_data
3. get_line_data
4. get_gen_data
5. get_voltage_profile
6. get_loading_profile
7. get_power_balance
8. get_line_results
9. get_bus_results

**Simulation Tools (7):**
1. run_power_flow (supports nr/fdBX/gs algorithms)
2. run_dc_power_flow
3. run_n1_contingency
4. run_short_circuit
5. run_opf
6. save_network_snapshot
7. restore_network_snapshot

**Diagnostic Tools (4):**
1. run_full_diagnostics
2. check_overloads
3. check_voltage_violations
4. find_disconnected_areas

**Grid Action Tools (4):**
1. adjust_generation
2. curtail_load
3. switch_line
4. switch_shunt

### Key Parameters
- **Model:** GPT-4o
- **Temperature:** 0.3 (deterministic tool selection)
- **Max tokens:** 2000
- **Max tool calls:** 10 iterations
- **Voltage limits:** 0.95 - 1.05 pu
- **Loading limit:** 100%

### Data Flow
1. User provides query + network → Preprocessing
2. Preprocessing extracts evidence + triggers rules → Agent
3. Agent runs ReAct loop (max 10 iterations):
   - LLM reasons about problem
   - Selects tools via function calling
   - Executes tools on network
   - Observes results
   - Repeats until solution found
4. Agent generates diagnostic report + metadata

### Memory Features
- **Network Snapshots:** Save/restore network state for safe experimentation
- **Conversation History:** Full message log for reproducibility
- **Tool Call Logs:** Complete audit trail of all tool invocations

---

## Integration into Paper

### Recommended Placement
Place the architecture diagram in Section V.E (GridDebugAgent) before the trajectory figure.

### Suggested Text Flow
1. **Problem setup** (what GridDebugAgent solves)
2. **Architecture diagram** (`fig:griddebug_architecture`) with description
3. **Trajectory examples** (`fig:griddebug_trajectory`) showing system in action
4. **Results tables** (repair rates, tool usage, etc.)

### Example Integration
```latex
\subsection{GridDebugAgent Architecture}

We implement GridDebugAgent as a ReAct-style \cite{yao2023react} agentic
system for power flow failure diagnosis and remediation.
Figure~\ref{fig:griddebug_architecture} shows the complete system architecture.

\input{griddebug_architecture.tex}

The system consists of six major components. The \textbf{preprocessing pipeline}
uses a rule-based evidence collector and rule engine to extract network metrics
and classify failures. The \textbf{agent core} implements a ReAct loop with
GPT-4o (temperature 0.3, max 10 iterations) using OpenAI function calling to
select and execute tools. The system provides \textbf{23 tools} across four
categories: Query tools (9) for network inspection, Simulation tools (7) for
power flow and contingency analysis, Diagnostic tools (4) for violation
detection, and Grid Action tools (4) for remediation. \textbf{Memory management}
enables safe experimentation through network snapshots and maintains full
conversation history for reproducibility.

Figure~\ref{fig:griddebug_trajectory} illustrates two representative trajectories...
```

---

## Next Steps

1. **Choose diagram format:**
   - Use Mermaid for quick iteration and web documentation
   - Use TikZ for final paper submission

2. **Review and refine:**
   - Check if all 23 tools need to be listed or can be abbreviated
   - Adjust layout/spacing for your paper's column width
   - Verify colors render well in grayscale (for print)

3. **Add to paper:**
   - Insert TikZ figure into Section V.E
   - Update caption if needed
   - Add cross-references in text
   - Ensure figure placement doesn't break page layout

4. **Validate accuracy:**
   - Compare diagram against actual implementation
   - Verify tool counts (Query: 9, Simulation: 7, Diagnostic: 4, Actions: 4)
   - Check parameter values (temp=0.3, max_calls=10, v_min=0.95, v_max=1.05)

---

## Source Files Referenced

All information in these diagrams comes directly from the students' implementation:

- `backend/agents/agentic_pipeline.py` - Agent core, ReAct loop, system prompts
- `backend/tools/query_tools.py` - 9 query tools
- `backend/tools/simulation_tools.py` - 7 simulation tools, snapshot management
- `backend/tools/diagnostic_tools.py` - 4 diagnostic tools
- `backend/tools/grid_actions.py` - 4 grid action tools
- `backend/rule_engine/preprocessor.py` - Evidence collector, rule engine

**Total:** 23 tools across 4 categories (verified against TOOL_DEFINITIONS in source code)
