"""methods/: one folder per evaluated method, holding its prompt text and a ``method.json``.

This package is the single source of truth for every prompt string the benchmark and the
Streamlit app use. ``methods/agent/prompts.py``, ``methods/prompting/prompt_variants.py``, ``methods/agent/engine.py`` and
``methods/prompting/prompts_baseline.py`` import their constants from here, so editing a ``.txt``
file changes the prompt everywhere, and ``tests/test_methods_prompts.py`` pins the SHA-256
prefix of every text to the value stamped on the runs behind the paper tables. A wording
change therefore fails a test until the pinned hash is updated on purpose.

Layout::

    methods/
      _shared/            texts several methods share (agent system prompt, LLM-only template)
      <method>/method.json  what the method is, how the runner names it, which texts it uses
      <method>/*.txt        texts specific to that method

Texts are read as bytes and decoded as UTF-8 with no stripping, so a trailing newline in
the file is part of the prompt. Do not "clean up" whitespace in these files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

METHODS_DIR = Path(__file__).resolve().parent


def read_text(rel_path: str) -> str:
    """Exact text of ``methods/<rel_path>`` (UTF-8, nothing stripped); a method-local file of an
    archived method is found under ``methods/_archive/`` too."""
    p = METHODS_DIR / rel_path
    if not p.is_file() and (METHODS_DIR / "_archive" / rel_path).is_file():
        p = METHODS_DIR / "_archive" / rel_path
    return p.read_bytes().decode("utf-8")


def prompt_hash(text: str) -> str:
    """12-hex-char SHA-256 prefix, the same function as ``methods.agent.prompts.prompt_hash``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Method:
    """One ``method.json``. ``runner_name`` is what ``evaluation/runner.py --method`` expects; ``code`` points
    at the file and function that run the method (see docs/ARCHITECTURE.md)."""

    folder: str
    runner_name: str
    group: str
    kind: str  # llm_only | engine | rule_based
    description: str
    uses_llm: bool
    uses_tools: bool
    gate: bool
    final_gate: bool
    strategy: Optional[str] = None
    architecture: Optional[str] = None
    memory: bool = False
    forced: bool = False
    probe: bool = False
    preload_case: bool = False
    prompt_files: List[str] = field(default_factory=list)
    dynamic_parts: List[str] = field(default_factory=list)
    archived: bool = False  # under methods/_archive: runnable and scorable, but not part of the current design
    code: str = ""  # where the code that runs this method lives (file: function)

    @property
    def path(self) -> Path:
        return (METHODS_DIR / "_archive" / self.folder) if self.archived else (METHODS_DIR / self.folder)


def _load_method(folder: Path) -> Method:
    data: Dict[str, Any] = json.loads((folder / "method.json").read_text(encoding="utf-8"))
    data.setdefault("folder", folder.name)
    data["archived"] = folder.parent.name == "_archive"
    return Method(**data)


def list_methods(include_archived: bool = True) -> List[Method]:
    """Every method with a ``method.json``, in a stable order. ``methods/_archive/`` holds the
    variants that are not part of the current design (kept so their old runs still render and
    rescore); ``include_archived=False`` lists only the current design."""
    found = {p.parent.name: _load_method(p.parent) for p in list(METHODS_DIR.glob("*/method.json")) + list(METHODS_DIR.glob("_archive/*/method.json"))}
    if not include_archived:
        found = {k: v for k, v in found.items() if not v.archived}
    order = [  # the six methods of the current design first (paper-table order), then the archive
        "rule_based", "llm_only_structured", "llm_only_cot", "plan_act_nogate", "react_nogate", "pfagent",
        "llm_only_few_shot", "llm_only_rag", "llm_only_nr",
        "llm_only_forced_structured", "llm_only_forced_cot", "formulation_probe_structured", "formulation_probe_cot",
        "single_call_structured", "single_call_few_shot", "single_call_cot", "single_call_rag",
        "react", "plan_act", "pfagent_obsgate",
    ]
    ordered = [found.pop(n) for n in order if n in found]
    return ordered + [found[k] for k in sorted(found)]


def get_method(name: str) -> Method:
    """Look a method up by folder name (``react``) or runner name (``llm_only:cot``)."""
    for m in list_methods():
        if name in (m.folder, m.runner_name):
            return m
    known = ", ".join(m.folder for m in list_methods())
    raise KeyError(f"unknown method {name!r}; known: {known}")


def folder_for_runner_name(runner_name: str) -> str:
    return get_method(runner_name).folder


# ---------------------------------------------------------------------------
# Assembled system prompts. These mirror, byte for byte, what the runner sends as the
# system message for each method, so ``prompt_hash(system_prompt_for(m))`` equals the
# ``system_prompt_hash`` stamped on that method's rows in report.json.
# ---------------------------------------------------------------------------


def system_prompt_for(method: str | Method, *, tool_variant: str = "v1") -> Optional[str]:
    """System message the runner uses for ``method`` (None for rule_based).

    The user message is built per request (case tables, retrieved rows, examples) and is not
    reproduced here; ``evaluation/experiment_report.py`` rebuilds one offline if needed.
    """
    m = method if isinstance(method, Method) else get_method(method)
    if m.kind == "rule_based":
        return None
    if m.kind == "llm_only" and m.probe:
        return read_text("_shared/formulation_probe_system_prompt.txt") + (read_text("_shared/cot_system_suffix.txt") if m.strategy == "cot" else "")
    if m.kind == "llm_only":
        # Same assembly as methods.prompting.prompt_variants._build_llm_only.
        base = read_text("_shared/llm_only_system_prompt.txt").strip()
        if m.forced:
            clause = read_text("llm_only_forced_structured/escape_clause_removed.txt")
            repl = read_text("llm_only_forced_structured/forced_replacement.txt")
            base = base.replace(clause, repl) if clause in base else base.rstrip() + "\n" + repl
        if m.strategy in ("cot", "nr"):
            base += read_text("_shared/cot_system_suffix.txt")
        return base
    agent = read_text("_shared/agent_system_prompt.txt")
    if m.architecture == "single_call":
        return agent.strip() + "\n\n" + read_text("single_call_structured/task_statement.txt")
    return agent


def planner_prompt_for(method: str | Method, *, tool_variant: str = "v1", plan_variant: str = "text") -> Optional[str]:
    """Plan-and-Act's planner system prompt (None for other architectures)."""
    m = method if isinstance(method, Method) else get_method(method)
    if m.architecture != "plan_act":
        return None
    if plan_variant == "structured":
        return read_text("plan_act_nogate/plan_system_prompt_structured.txt")
    from methods.agent.tools import tools_catalog_text  # local import: llm imports this package

    return read_text("plan_act_nogate/plan_system_prompt_prefix.txt") + tools_catalog_text(tool_variant, with_enums=True)


def describe(method: str | Method, *, tool_variant: str = "v1") -> str:
    """Human-readable card for ``run.py show-prompt``."""
    m = method if isinstance(method, Method) else get_method(method)
    lines = [
        f"# {m.folder}   (runner name: {m.runner_name})",
        f"group:        {m.group}",
        f"kind:         {m.kind}" + (f"   architecture: {m.architecture}" if m.architecture else "") + (f"   strategy: {m.strategy}" if m.strategy else ""),
        f"gate:         in-loop={m.gate}   final={m.final_gate}   memory={m.memory}",
        f"uses:         llm={m.uses_llm}   tools={m.uses_tools}",
        f"description:  {m.description}",
        "prompt files: " + (", ".join(m.prompt_files) if m.prompt_files else "(none)"),
        "dynamic parts:" + ("".join(f"\n  - {d}" for d in m.dynamic_parts) if m.dynamic_parts else " (none)"),
    ]
    sp = system_prompt_for(m, tool_variant=tool_variant)
    if sp is not None:
        lines += ["", f"## system prompt   (hash {prompt_hash(sp)})", sp]
    pp = planner_prompt_for(m, tool_variant=tool_variant)
    if pp is not None:
        lines += ["", f"## planner prompt   (hash {prompt_hash(pp)}, tool variant {tool_variant})", pp]
    return "\n".join(lines)


__all__ = [
    "METHODS_DIR", "Method", "read_text", "prompt_hash", "list_methods", "get_method",
    "folder_for_runner_name", "system_prompt_for", "planner_prompt_for", "describe",
]
