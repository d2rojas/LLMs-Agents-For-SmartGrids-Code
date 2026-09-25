"""prompting/prompt_variants.py

Single-call prompting strategies for the paper's Section 3 ablation.

Four strategies (structured / few-shot / chain-of-thought / RAG) are built on
identical power-flow requests in two modes:

- ``llm_only``: the LLM must answer from the case data in the prompt (no tools).
  The structured variant reuses ``prompting.llm_only.build_baseline_prompt`` so
  results remain comparable with the published LLM-only baseline, and every
  strategy keeps the *same* output-format section so
  ``prompting.llm_only.parse_llm_baseline_json`` keeps working.
- ``single_call``: the LLM receives the tool definitions (``agent.tools.TOOLS``,
  passed to the API by the caller via ``get_openai_tools()``) and must emit the
  tool calls in one round: no memory, no planning loop.

This module only builds messages; it never calls an LLM and has no new
dependencies. Pure functions, no agent framework.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from prompting.llm_only import build_baseline_prompt
from prompting.prompts_baseline import BASELINE_PROMPT_TEMPLATE, BASELINE_SYSTEM_PROMPT
from agent.prompts import SYSTEM_PROMPT_EN as SYSTEM_PROMPT
from agent.tools import TOOLS, tools_catalog_text
from methods import read_text as _read_method_text

STRATEGIES: Tuple[str, ...] = ("structured", "few_shot", "cot", "rag", "nr")
MODES: Tuple[str, ...] = ("llm_only", "single_call")

# Section headings shared by every strategy (used by ``context_stats``).
CONTEXT_HEADING = "## System Data"
TASK_HEADING = "## Task"
EXAMPLES_HEADING = "## Worked Examples"
REASONING_HEADING = "## Reasoning Instructions"
OUTPUT_HEADING = "## Output Requirements"
EXAMPLE_HEADING_PREFIX = "### Example "

TRAFO_LINE_ID_OFFSET = 100000  # same convention as the baseline prompt

# ---------------------------------------------------------------------------
# Output-format sections (identical within a mode, by construction)
# ---------------------------------------------------------------------------


def _split_baseline_template() -> Tuple[str, str]:
    """Split the baseline user template into (role+context, output-format)."""
    head, sep, tail = BASELINE_PROMPT_TEMPLATE.partition(OUTPUT_HEADING)
    if not sep:  # pragma: no cover - template contract
        raise RuntimeError("BASELINE_PROMPT_TEMPLATE has no '## Output Requirements' section")
    return head, sep + tail


# ``.format()`` with no arguments collapses the template's escaped ``{{ }}`` braces,
# exactly as ``build_baseline_prompt`` does for the structured baseline.
_BASELINE_OUTPUT_SECTION = _split_baseline_template()[1].format().strip()

LLM_ONLY_BUS_ID_NOTE = _read_method_text("_shared/llm_only_bus_id_note.txt")

# 2026-09-25 (v2): every method replies with the same JSON object (methods/_shared/output_contract.txt).
LLM_ONLY_OUTPUT_SECTION = _read_method_text("_shared/output_contract.txt")

SINGLE_CALL_OUTPUT_SECTION = _read_method_text("single_call_structured/output_section.txt")

SINGLE_CALL_TASK_STATEMENT = _read_method_text("single_call_structured/task_statement.txt")

FORCED_ESCAPE_CLAUSE = _read_method_text("llm_only_forced_structured/escape_clause_removed.txt")
FORCED_REPLACEMENT = _read_method_text("llm_only_forced_structured/forced_replacement.txt")


def forced_system_prompt(base: str) -> str:
    """The baseline system prompt without the escape clause (forced best-effort variant)."""
    if FORCED_ESCAPE_CLAUSE in base:
        return base.replace(FORCED_ESCAPE_CLAUSE, FORCED_REPLACEMENT)
    return base.rstrip() + "\n" + FORCED_REPLACEMENT


COT_SYSTEM_SUFFIX = _read_method_text("_shared/cot_system_suffix.txt")

# 2026-09-23: Formulation for the prompting rows is measured with a companion probe that asks
# only for the formulation (which solver operations the request needs), never for numbers.
# The answer prompts above stay byte-identical to the paper runs; asking for the formulation
# inside the answer changed gpt-4o-mini's chain-of-thought behaviour (it stopped abstaining).
OPERATIONS_SECTION = _read_method_text("_shared/operations_section.txt")


def operations_section(tool_variant: str = "load_split") -> str:
    """'## Operations': the catalogue (names, arguments, allowed values, meanings) a no-tools answer
    uses to fill the `formulation` field of the common output contract."""
    return OPERATIONS_SECTION + tools_catalog_text(tool_variant, with_enums=True)


FORMULATION_PROBE_SYSTEM_PROMPT = _read_method_text("_shared/formulation_probe_system_prompt.txt")
FORMULATION_PROBE_SECTION = _read_method_text("_shared/formulation_probe_section.txt")
FORMULATION_PROBE_OUTPUT_SECTION = _read_method_text("_shared/formulation_probe_output_section.txt")


def formulation_probe_section(tool_variant: str = "load_split") -> str:
    """The probe's '## Formulation' section: fixed instruction plus the tool catalogue of ``tool_variant``."""
    return FORMULATION_PROBE_SECTION + tools_catalog_text(tool_variant, with_enums=True)

LLM_ONLY_COT_SECTION = _read_method_text("llm_only_cot/reasoning_section.txt")

LLM_ONLY_NR_SECTION = _read_method_text("llm_only_nr/reasoning_section.txt")

SINGLE_CALL_COT_SECTION = _read_method_text("single_call_cot/reasoning_section.txt")


# ---------------------------------------------------------------------------
# Compact case rows (shared by structured single_call and RAG)
# ---------------------------------------------------------------------------


@dataclass
class Row:
    """One retrievable unit of case context (a bus or a branch)."""

    kind: str  # "bus" | "line" | "trafo"
    key: int  # display bus id, or line_id (trafo: 100000 + trafo index)
    text: str
    buses: Set[int] = field(default_factory=set)
    tokens: Set[str] = field(default_factory=set)
    is_slack: bool = False
    has_load: bool = False
    has_gen: bool = False


def _fmt(x: Any) -> str:
    try:
        return f"{float(x):.4g}"
    except Exception:
        return str(x)


def _display_bus_id(net: Any, bus_idx: int) -> int:
    """Display id of a pandapower bus row: bus.name as int if possible, else index+1."""
    try:
        name = net.bus.at[bus_idx, "name"]
        return int(str(name).strip())
    except Exception:
        return int(bus_idx) + 1


_STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "at", "by", "for", "in", "is", "it", "me", "of", "on", "or", "the", "then",
    "to", "with", "what", "which", "whether", "any", "all", "now", "please", "tell", "check", "report",
}


def _tokens(text: str) -> Set[str]:
    raw = re.findall(r"[a-z0-9][a-z0-9_\-\.]*", text.lower())
    return {t.strip("._-") for t in raw if t.strip("._-")} - _STOPWORDS


def _sum_by_bus(df: Any, col: str) -> Dict[int, float]:
    out: Dict[int, float] = {}
    if df is None or len(df) == 0 or col not in df.columns:
        return out
    for bus, val in zip(df["bus"].tolist(), df[col].tolist()):
        try:
            out[int(bus)] = out.get(int(bus), 0.0) + float(val)
        except Exception:
            continue
    return out


def _bus_rows(net: Any) -> List[Row]:
    load_p = _sum_by_bus(getattr(net, "load", None), "p_mw")
    load_q = _sum_by_bus(getattr(net, "load", None), "q_mvar")
    gen_p = _sum_by_bus(getattr(net, "gen", None), "p_mw")
    gen_vm = _sum_by_bus(getattr(net, "gen", None), "vm_pu")
    ext = getattr(net, "ext_grid", None)
    slack_idx: Set[int] = set(int(b) for b in ext["bus"].tolist()) if ext is not None and len(ext) else set()

    rows: List[Row] = []
    for idx in net.bus.index.tolist():
        idx = int(idx)
        did = _display_bus_id(net, idx)
        parts = [f"bus {did}", f"{_fmt(net.bus.at[idx, 'vn_kv'])} kV"]
        has_load = idx in load_p
        has_gen = idx in gen_p
        is_slack = idx in slack_idx
        if has_load:
            parts.append(f"load {_fmt(load_p[idx])} MW {_fmt(load_q.get(idx, 0.0))} Mvar")
        if has_gen:
            parts.append(f"gen {_fmt(gen_p[idx])} MW vm {_fmt(gen_vm.get(idx, 1.0))} pu")
        if is_slack:
            vm = ext.loc[ext["bus"] == idx, "vm_pu"].iloc[0]
            parts.append(f"slack/reference vm {_fmt(vm)} pu")
        text = " | ".join(parts)
        rows.append(
            Row(
                kind="bus",
                key=did,
                text=text,
                buses={did},
                tokens=_tokens(text) | {"bus", "voltage"},
                is_slack=is_slack,
                has_load=has_load,
                has_gen=has_gen,
            )
        )
    return rows


def _line_rows(net: Any) -> List[Row]:
    rows: List[Row] = []
    line = getattr(net, "line", None)
    if line is not None and len(line):
        for idx in line.index.tolist():
            idx = int(idx)
            fb = _display_bus_id(net, int(line.at[idx, "from_bus"]))
            tb = _display_bus_id(net, int(line.at[idx, "to_bus"]))
            text = (
                f"line {idx} | {fb}-{tb} | r {_fmt(line.at[idx, 'r_ohm_per_km'])} x {_fmt(line.at[idx, 'x_ohm_per_km'])} "
                f"ohm/km | len {_fmt(line.at[idx, 'length_km'])} km | max_i {_fmt(line.at[idx, 'max_i_ka'])} kA"
                f"{'' if bool(line.at[idx, 'in_service']) else ' | OUT OF SERVICE'}"
            )
            rows.append(
                Row(kind="line", key=idx, text=text, buses={fb, tb}, tokens=_tokens(text) | {"line", "branch"})
            )
    trafo = getattr(net, "trafo", None)
    if trafo is not None and len(trafo):
        for idx in trafo.index.tolist():
            idx = int(idx)
            hv = _display_bus_id(net, int(trafo.at[idx, "hv_bus"]))
            lv = _display_bus_id(net, int(trafo.at[idx, "lv_bus"]))
            lid = TRAFO_LINE_ID_OFFSET + idx
            text = (
                f"trafo {lid} | {hv}-{lv} | sn {_fmt(trafo.at[idx, 'sn_mva'])} MVA | "
                f"vk {_fmt(trafo.at[idx, 'vk_percent'])} % | {_fmt(trafo.at[idx, 'vn_hv_kv'])}/{_fmt(trafo.at[idx, 'vn_lv_kv'])} kV"
                f"{'' if bool(trafo.at[idx, 'in_service']) else ' | OUT OF SERVICE'}"
            )
            rows.append(
                Row(
                    kind="trafo",
                    key=lid,
                    text=text,
                    buses={hv, lv},
                    tokens=_tokens(text) | {"line", "branch", "transformer", "trafo"},
                )
            )
    return rows


def case_rows(net: Any) -> Tuple[List[Row], List[Row]]:
    """Compact one-line rows for every bus and every branch (lines + trafos)."""
    return _bus_rows(net), _line_rows(net)


def _n_rows(df: Any) -> int:
    return 0 if df is None else int(len(df))


def case_summary_line(net: Any, case_name: str) -> str:
    n_bus = _n_rows(net.bus)
    n_line = _n_rows(getattr(net, "line", None))
    n_trafo = _n_rows(getattr(net, "trafo", None))
    load = getattr(net, "load", None)
    total_load = float(load["p_mw"].sum()) if load is not None and len(load) else 0.0
    return (
        f"Case {case_name}: {n_bus} buses, {n_line} lines, {n_trafo} transformers, "
        f"total load {_fmt(total_load)} MW. Bus ids are IEEE display ids (1..N); "
        f"line_id is the net.line row index, transformers use {TRAFO_LINE_ID_OFFSET}+row index."
    )


def _rows_text(bus_rows: Sequence[Row], line_rows: Sequence[Row]) -> str:
    out = ["### Buses"] + [r.text for r in bus_rows] + ["", "### Branches"] + [r.text for r in line_rows]
    return "\n".join(out)


def _tools_text(tools: Iterable[Dict[str, Any]]) -> str:
    lines = ["### Available tools"]
    for t in tools:
        props = t.get("parameters", {}).get("properties", {}) or {}
        args = ", ".join(props.keys()) if props else "no arguments"
        lines.append(f"- {t['name']}({args}): {t['description']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# RAG retrieval
# ---------------------------------------------------------------------------

_UNIT_LOOKAHEAD = r"(?!\s*(?:mw|mvar|kv|kva|mva|%|pu|p\.u\.))"
# "bus 3", "buses 3, 5 and 7" (a number followed by a unit is a value, not a bus id)
_BUS_MENTION_RE = re.compile(
    r"\bbus(?:es)?\s*#?\s*(\d+" + _UNIT_LOOKAHEAD + r"(?:\s*(?:,|and|&)\s*(?:bus\s*)?\d+" + _UNIT_LOOKAHEAD + r")*)",
    re.IGNORECASE,
)
# "line 7" / "branch 7" as a line_id (but not "line 1-5", which is a bus pair)
_LINE_ID_RE = re.compile(
    r"\b(?:line|branch|trafo|transformer)\s*#?\s*(\d+)\b(?!\s*(?:-|–|to|and)\s*(?:bus\s*)?\d)", re.IGNORECASE
)
# "1-5", "1 to 5", "between bus 4 and bus 9", "from bus 4 to bus 9"
_PAIR_RE = re.compile(r"\b(\d+)\s*(?:-|–|—|->|to)\s*(\d+)\b" + _UNIT_LOOKAHEAD)
_BUS_PAIR_RE = re.compile(r"\bbus\s*(\d+)\s*(?:and|to|-|–|with)\s*(?:bus\s*)?(\d+)\b" + _UNIT_LOOKAHEAD, re.IGNORECASE)

# tokens present in nearly every row; they contribute via keyword boosts, not lexical overlap
_GENERIC_TOKENS: Set[str] = {
    "bus", "line", "trafo", "branch", "load", "gen", "slack", "reference", "vm", "pu", "mw", "mvar",
    "kv", "ka", "mva", "ohm", "ohm/km", "km", "len", "max_i", "r", "x", "sn", "vk", "out", "of", "service",
    "voltage", "transformer", "1", "1.0",
}

# keyword -> (row kinds boosted, bus attribute boosted)
_KEYWORD_BOOSTS: Dict[str, Tuple[Set[str], Optional[str]]] = {
    "load": ({"bus"}, "has_load"),
    "loads": ({"bus"}, "has_load"),
    "demand": ({"bus"}, "has_load"),
    "mw": ({"bus"}, "has_load"),
    "mvar": ({"bus"}, "has_load"),
    "shed": ({"bus"}, "has_load"),
    "voltage": ({"bus"}, "has_gen"),
    "voltages": ({"bus"}, "has_gen"),
    "pu": ({"bus"}, "has_gen"),
    "p.u.": ({"bus"}, "has_gen"),
    "generator": ({"bus"}, "has_gen"),
    "generators": ({"bus"}, "has_gen"),
    "gen": ({"bus"}, "has_gen"),
    "slack": ({"bus"}, "is_slack"),
    "line": ({"line", "trafo"}, None),
    "lines": ({"line", "trafo"}, None),
    "branch": ({"line", "trafo"}, None),
    "branches": ({"line", "trafo"}, None),
    "overload": ({"line", "trafo"}, None),
    "overloaded": ({"line", "trafo"}, None),
    "loading": ({"line", "trafo"}, None),
    "thermal": ({"line", "trafo"}, None),
    "flow": ({"line", "trafo"}, None),
    "flows": ({"line", "trafo"}, None),
    "contingency": ({"line", "trafo"}, None),
    "n-1": ({"line", "trafo"}, None),
    "outage": ({"line", "trafo"}, None),
    "disconnect": ({"line", "trafo"}, None),
    "trip": ({"line", "trafo"}, None),
    "transformer": ({"trafo"}, None),
    "transformers": ({"trafo"}, None),
    "trafo": ({"trafo"}, None),
}

# request keywords that map to tool names (lexical synonyms for tool retrieval)
_TOOL_SYNONYMS: Dict[str, Set[str]] = {
    "load_case": {"load case", "case14", "case30", "case57", "case118", "case300", "switch case"},
    "run_powerflow": {"power flow", "powerflow", "run", "solve", "voltage", "voltages", "flows", "losses", "slack", "total load", "total generation"},
    "modify_load": {"load", "demand", "set load", "increase", "decrease", "mw", "mvar", "shed"},
    "disconnect_line": {"disconnect", "outage", "trip", "open", "remove line", "take out"},
    "reconnect_line": {"reconnect", "restore", "close", "back in service"},
    "get_most_loaded_branch": {"most loaded", "overload", "overloaded", "loading", "thermal", "heaviest"},
    "run_n1_contingency": {"n-1", "n1", "contingency", "contingencies", "worst", "rank"},
    "recommend_remedial_actions": {"remedial", "mitigate", "mitigation", "fix", "relieve", "recommend"},
    "apply_remedial_action": {"apply", "execute action"},
    "get_status": {"status", "state", "current network", "summary", "total load", "how many", "what is"},
    "generate_plot": {"plot", "heatmap", "diagram", "visualize", "chart", "figure"},
}


def _mentioned_buses(request_text: str) -> Set[int]:
    out: Set[int] = set()
    for m in _BUS_MENTION_RE.finditer(request_text):
        out.update(int(n) for n in re.findall(r"\d+", m.group(1)))
    return out


def _mentioned_line_ids(request_text: str) -> Set[int]:
    return {int(m.group(1)) for m in _LINE_ID_RE.finditer(request_text)}


def _mentioned_pairs(request_text: str) -> Set[Tuple[int, int]]:
    """Explicit bus pairs: 'a-b', 'a to b', 'between bus a and bus b', 'from bus a to bus b'."""
    pairs = {(int(a), int(b)) for a, b in _PAIR_RE.findall(request_text)}
    pairs |= {(int(a), int(b)) for a, b in _BUS_PAIR_RE.findall(request_text)}
    return {(a, b) for a, b in pairs if a != b}


def _score_row(row: Row, req_tokens: Set[str], mentioned_buses: Set[int], pairs: Set[Tuple[int, int]]) -> float:
    informative = {t for t in row.tokens & req_tokens if t not in _GENERIC_TOKENS and not t.replace(".", "").isdigit()}
    score = float(len(informative))
    for kw, (kinds, attr) in _KEYWORD_BOOSTS.items():
        if kw in req_tokens and row.kind in kinds:
            score += 1.0
            if attr and getattr(row, attr):
                score += 1.0
    if row.kind != "bus":
        if row.buses & mentioned_buses:
            score += 3.0  # branch adjacent to a mentioned bus
        if any({a, b} == row.buses for a, b in pairs):
            score += 10.0
    return score


def _forced(row: Row, mentioned_buses: Set[int], mentioned_lines: Set[int], pairs: Set[Tuple[int, int]]) -> bool:
    if row.kind == "bus":
        return row.is_slack or row.key in mentioned_buses
    if row.key in mentioned_lines:
        return True
    return any({a, b} == row.buses for a, b in pairs)


def _score_tools(req_tokens: Set[str], request_text: str) -> List[Dict[str, Any]]:
    low = request_text.lower()
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for t in TOOLS:
        name_tokens = set(t["name"].split("_"))
        score = float(len((name_tokens | _tokens(t["description"])) & req_tokens))
        score += sum(2.0 for syn in _TOOL_SYNONYMS.get(t["name"], set()) if syn in low)
        if score > 0:
            scored.append((score, t))
    scored.sort(key=lambda st: (-st[0], st[1]["name"]))
    picked = [t for _, t in scored[:4]]
    if not picked:
        picked = [t for t in TOOLS if t["name"] in ("run_powerflow", "get_status")]
    return picked


def retrieve_context(request_text: str, net: Any, k_rows: int = 8) -> Dict[str, Any]:
    """Retrieve the case rows and tool descriptions most relevant to ``request_text``.

    Scoring is lexical overlap between request tokens and each compact row plus
    keyword boosts (load/voltage/line/overload/contingency...). The slack bus and
    every explicitly mentioned bus / line are always kept; the remaining budget up
    to ``k_rows`` is filled by score. Returns compact text plus matching tools.
    """
    if k_rows < 1:
        raise ValueError("k_rows must be >= 1")

    req_tokens = _tokens(request_text) | ({"n-1"} if re.search(r"\bn\s*-\s*1\b", request_text, re.I) else set())
    mentioned_buses = _mentioned_buses(request_text)
    mentioned_lines = _mentioned_line_ids(request_text)
    pairs = _mentioned_pairs(request_text)

    bus_rows, line_rows = case_rows(net)
    all_rows = bus_rows + line_rows

    forced = [r for r in all_rows if _forced(r, mentioned_buses, mentioned_lines, pairs)]
    forced_ids = {id(r) for r in forced}
    rest = [r for r in all_rows if id(r) not in forced_ids]
    rest.sort(key=lambda r: (-_score_row(r, req_tokens, mentioned_buses, pairs), r.kind != "bus", r.key))

    budget = max(0, k_rows - len(forced))
    selected = forced + rest[:budget]
    sel_ids = {id(r) for r in selected}
    sel_bus = [r for r in bus_rows if id(r) in sel_ids]
    sel_line = [r for r in line_rows if id(r) in sel_ids]

    tools = _score_tools(req_tokens, request_text)
    return {
        "bus_rows": [r.text for r in sel_bus],
        "line_rows": [r.text for r in sel_line],
        "tools": [{"name": t["name"], "description": t["description"]} for t in tools],
        "tool_defs": tools,
        "mentioned_buses": sorted(mentioned_buses),
        "mentioned_lines": sorted(mentioned_lines),
        "n_rows_selected": len(selected),
        "n_rows_total": len(all_rows),
        "k_rows": k_rows,
        "text": _rows_text(sel_bus, sel_line),
    }


# ---------------------------------------------------------------------------
# Few-shot demonstrations (fictional tiny case; never the evaluated case)
# ---------------------------------------------------------------------------

_FEW_SHOT_LLM_ONLY: List[Tuple[str, str]] = [
    (
        "Run the AC power flow on this 3-bus example system and report all voltages and flows.",
        "```json\n"
        '{"converged": true,\n'
        ' "bus_voltages": [{"bus_id": 1, "vm_pu": 1.05, "va_deg": 0.0},\n'
        '                  {"bus_id": 2, "vm_pu": 1.012, "va_deg": -2.4},\n'
        '                  {"bus_id": 3, "vm_pu": 0.987, "va_deg": -4.1}],\n'
        ' "line_flows": [{"line_id": 0, "p_from_mw": 61.3, "loading_percent": 48.2},\n'
        '                {"line_id": 1, "p_from_mw": 30.9, "loading_percent": 25.7}],\n'
        ' "total_generation_mw": 91.8, "total_load_mw": 90.0, "total_loss_mw": 1.8}\n'
        "```",
    ),
    (
        "In the same 3-bus example, set the load at bus 3 to 60 MW and report the new power flow.",
        "```json\n"
        '{"converged": true,\n'
        ' "bus_voltages": [{"bus_id": 1, "vm_pu": 1.05, "va_deg": 0.0},\n'
        '                  {"bus_id": 2, "vm_pu": 1.004, "va_deg": -3.3},\n'
        '                  {"bus_id": 3, "vm_pu": 0.941, "va_deg": -6.2}],\n'
        ' "line_flows": [{"line_id": 0, "p_from_mw": 82.9, "loading_percent": 66.0},\n'
        '                {"line_id": 1, "p_from_mw": 40.6, "loading_percent": 34.1}],\n'
        ' "total_generation_mw": 123.4, "total_load_mw": 120.0, "total_loss_mw": 3.4}\n'
        "```",
    ),
]

# (request, ordered tool calls) -- names/args are validated against TOOLS in tests
_FEW_SHOT_SINGLE_CALL: List[Tuple[str, List[Tuple[str, Dict[str, Any]]]]] = [
    (
        "Disconnect the line between bus 2 and bus 4 and tell me which branch is now the most loaded.",
        [("disconnect_line", {"from_bus": 2, "to_bus": 4}), ("get_most_loaded_branch", {})],
    ),
    (
        "Set the load at bus 5 to 40 MW and 10 Mvar, then rank the 3 worst N-1 contingencies by overload.",
        [
            ("modify_load", {"bus_id": 5, "p_mw": 40, "q_mvar": 10}),
            ("run_n1_contingency", {"top_k": 3, "criteria": "max_overload"}),
        ],
    ),
]

FEW_SHOT_DISCLAIMERS: Dict[str, str] = {
    "llm_only": (
        "The examples below use a FICTIONAL tiny 3-bus/2-line system that is NOT the case in this "
        "prompt; their numbers are illustrative only and must not be copied. They show the expected "
        "answer shape."
    ),
    "single_call": (
        "The examples below refer to a DIFFERENT, fictional small system, not the case in this prompt; "
        "they show which tools to call, with which arguments and in which order."
    ),
}


def _render_tool_calls(calls: Sequence[Tuple[str, Dict[str, Any]]]) -> str:
    lines = []
    for i, (name, args) in enumerate(calls, start=1):
        rendered = ", ".join(f"{k}={v!r}" if not isinstance(v, str) else f'{k}="{v}"' for k, v in args.items())
        lines.append(f"{i}. {name}({rendered})")
    return "\n".join(lines)


def few_shot_section(mode: str) -> str:
    """Exactly two worked demonstrations for ``mode``."""
    blocks = [EXAMPLES_HEADING, FEW_SHOT_DISCLAIMERS[mode], ""]
    if mode == "llm_only":
        for i, (req, ans) in enumerate(_FEW_SHOT_LLM_ONLY, start=1):
            blocks += [f"{EXAMPLE_HEADING_PREFIX}{i}", f"Request: {req}", "Expected answer (example numbers):", ans, ""]
    else:
        for i, (req, calls) in enumerate(_FEW_SHOT_SINGLE_CALL, start=1):
            blocks += [f"{EXAMPLE_HEADING_PREFIX}{i}", f"Request: {req}", "Correct tool calls, in order:", _render_tool_calls(calls), ""]
    return "\n".join(blocks).rstrip()


def few_shot_tool_calls() -> List[Tuple[str, Dict[str, Any]]]:
    """Flat list of the single_call demonstration tool calls (for validation)."""
    return [call for _, calls in _FEW_SHOT_SINGLE_CALL for call in calls]


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------


def _validate(strategy: str, mode: str) -> None:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; expected one of {STRATEGIES}")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")


def _task_section(request_text: str) -> str:
    return f"{TASK_HEADING}\n{request_text.strip()}"


def _join(sections: Iterable[str]) -> str:
    return "\n\n".join(s.strip() for s in sections if s and s.strip())


def _llm_only_role_and_context(strategy: str, request_text: str, net: Any, case_name: str, k_rows: int) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Role + '## System Data' block. Structured/few_shot/cot reuse the baseline dump; rag retrieves."""
    if strategy != "rag":
        base = build_baseline_prompt(case_name, net)
        head, _, _ = base.partition(OUTPUT_HEADING)
        return head.strip(), None
    ctx = retrieve_context(request_text, net, k_rows=k_rows)
    role = f"You are a power systems expert. Based on the following IEEE {case_name} test system data, calculate the AC power flow results."
    context = (
        f"{CONTEXT_HEADING} (retrieved rows relevant to the request; {ctx['n_rows_selected']} of {ctx['n_rows_total']} rows)\n"
        f"{case_summary_line(net, case_name)}\n\n{ctx['text']}"
    )
    return _join([role, context]), ctx


def _build_formulation_probe(strategy: str, request_text: str, net: Any, case_name: str, k_rows: int, tool_variant: str) -> List[Dict[str, str]]:
    """Companion to the llm_only rows: same case tables and request, but the only output is the
    declared formulation. Strategies: structured (JSON straight away) or cot (reason first)."""
    role_ctx, _ = _llm_only_role_and_context(strategy, request_text, net, case_name, k_rows)
    sections: List[str] = [role_ctx, _task_section(request_text)]
    if strategy == "cot":
        sections.append(LLM_ONLY_COT_SECTION)
    sections.append(formulation_probe_section(tool_variant))
    sections.append(FORMULATION_PROBE_OUTPUT_SECTION)
    system = FORMULATION_PROBE_SYSTEM_PROMPT + (COT_SYSTEM_SUFFIX if strategy == "cot" else "")
    return [{"role": "system", "content": system}, {"role": "user", "content": _join(sections)}]


def _build_llm_only(strategy: str, request_text: str, net: Any, case_name: str, k_rows: int, forced: bool = False, tool_variant: str = "load_split", probe: bool = False) -> List[Dict[str, str]]:
    if probe:
        return _build_formulation_probe(strategy, request_text, net, case_name, k_rows, tool_variant)
    role_ctx, _ = _llm_only_role_and_context(strategy, request_text, net, case_name, k_rows)
    sections: List[str] = [role_ctx]
    if strategy == "few_shot":
        sections.append(few_shot_section("llm_only"))
    sections.append(_task_section(request_text))
    if strategy == "cot":
        sections.append(LLM_ONLY_COT_SECTION)
    elif strategy == "nr":
        sections.append(LLM_ONLY_NR_SECTION)
    sections.append(operations_section(tool_variant))
    sections.append(LLM_ONLY_OUTPUT_SECTION)

    base = forced_system_prompt(BASELINE_SYSTEM_PROMPT.strip()) if forced else BASELINE_SYSTEM_PROMPT.strip()
    system = base + (COT_SYSTEM_SUFFIX if strategy in ("cot", "nr") else "")
    return [{"role": "system", "content": system}, {"role": "user", "content": _join(sections)}]


def _single_call_context(strategy: str, request_text: str, net: Any, case_name: str, k_rows: int) -> str:
    if strategy != "rag":
        bus_rows, line_rows = case_rows(net)
        return _join(
            [
                f"{CONTEXT_HEADING} (compact, full case)\n{case_summary_line(net, case_name)}\n\n{_rows_text(bus_rows, line_rows)}",
                _tools_text(TOOLS),
            ]
        )
    ctx = retrieve_context(request_text, net, k_rows=k_rows)
    return _join(
        [
            f"{CONTEXT_HEADING} (retrieved rows relevant to the request; {ctx['n_rows_selected']} of {ctx['n_rows_total']} rows)\n"
            f"{case_summary_line(net, case_name)}\n\n{ctx['text']}",
            _tools_text(ctx["tool_defs"]),
        ]
    )


def _build_single_call(strategy: str, request_text: str, net: Any, case_name: str, k_rows: int) -> List[Dict[str, str]]:
    role = f"The network {case_name} is loaded. Use the tools to fulfil the request below."
    sections: List[str] = [role, _single_call_context(strategy, request_text, net, case_name, k_rows)]
    if strategy == "few_shot":
        sections.append(few_shot_section("single_call"))
    sections.append(_task_section(request_text))
    if strategy == "cot":
        sections.append(SINGLE_CALL_COT_SECTION)
    sections.append(SINGLE_CALL_OUTPUT_SECTION)

    system = SYSTEM_PROMPT.strip() + "\n\n" + SINGLE_CALL_TASK_STATEMENT
    return [{"role": "system", "content": system}, {"role": "user", "content": _join(sections)}]


def build_messages(
    strategy: str,
    mode: str,
    request_text: str,
    net: Any,
    case_name: str,
    *,
    k_rows: Optional[int] = None,
    forced: bool = False,
    tool_variant: str = "load_split",
    probe: bool = False,
) -> List[Dict[str, str]]:
    """Build OpenAI-style chat messages for one (strategy, mode) on ``request_text``.

    ``k_rows`` only affects ``strategy == "rag"`` (default 8). For ``single_call`` the
    caller passes ``agent.tools.get_openai_tools()`` as the API ``tools`` argument.
    """
    _validate(strategy, mode)
    if not request_text or not request_text.strip():
        raise ValueError("request_text must be non-empty")
    k = 8 if k_rows is None else int(k_rows)
    if mode == "llm_only":
        return _build_llm_only(strategy, request_text, net, case_name, k, forced=forced, tool_variant=tool_variant, probe=probe)
    return _build_single_call(strategy, request_text, net, case_name, k)


# ---------------------------------------------------------------------------
# Context size accounting (character count as a token proxy)
# ---------------------------------------------------------------------------


def _context_block(user_content: str) -> str:
    """Text from the '## System Data' heading up to the next '## ' heading."""
    start = user_content.find(CONTEXT_HEADING)
    if start < 0:
        return ""
    nxt = re.search(r"^## ", user_content[start + len(CONTEXT_HEADING) :], flags=re.MULTILINE)
    end = start + len(CONTEXT_HEADING) + nxt.start() if nxt else len(user_content)
    return user_content[start:end]


def context_stats(messages: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    """Character counts for a message list: total, system, user and the case-context block."""
    system_chars = sum(len(m.get("content") or "") for m in messages if m.get("role") == "system")
    user_msgs = [m.get("content") or "" for m in messages if m.get("role") == "user"]
    user_chars = sum(len(c) for c in user_msgs)
    context_chars = sum(len(_context_block(c)) for c in user_msgs)
    return {
        "n_messages": len(messages),
        "total_chars": system_chars + user_chars,
        "system_chars": system_chars,
        "user_chars": user_chars,
        "context_chars": context_chars,
    }
