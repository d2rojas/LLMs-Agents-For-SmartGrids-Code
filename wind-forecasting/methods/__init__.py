"""methods/: one folder per evaluated method, holding its ``method.json`` and its prompt texts.

The same registry API as the other case studies:

    methods.cards()            every method, in table order
    methods.card("windagent")  one card, as a dict
    methods.texts("llm_only_cot")   (relative path, text) for each prompt file the method uses
    methods.read_text("_shared/output_contract.txt")
    methods.prompt_hash(text)

The ``.txt`` files under ``methods/`` are the only copy of every fixed prompt
sentence. ``tests/test_methods_prompts.py`` pins the hash of each one, so a
wording change fails a test until the pin is updated on purpose. Texts are read
as bytes and decoded as UTF-8 with exactly one trailing newline stripped.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

METHODS_DIR = Path(__file__).resolve().parent

# The six methods of the design, in table order: the same six, with the same
# names, as every other case study. The set does not vary.
ORDER = ("rule_based", "llm_only_structured", "llm_only_cot", "plan_act_nogate", "react_nogate", "windagent")


def read_text(rel_path: str) -> str:
    p = METHODS_DIR / rel_path
    raw = p.read_bytes().decode("utf-8")
    return raw[:-1] if raw.endswith("\n") else raw


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _load(folder: str) -> Dict[str, Any]:
    d = json.loads((METHODS_DIR / folder / "method.json").read_text(encoding="utf-8"))
    d.setdefault("folder", folder)
    return d


def cards() -> List[Dict[str, Any]]:
    found = {p.parent.name: _load(p.parent.name) for p in METHODS_DIR.glob("*/method.json")}
    ordered = [found.pop(n) for n in ORDER if n in found]
    return ordered + [found[k] for k in sorted(found)]


def card(name: str) -> Dict[str, Any]:
    for c in cards():
        if name in (c["folder"], c.get("runner_name")):
            return c
    raise KeyError(f"unknown method {name!r}; known: {', '.join(c['folder'] for c in cards())}")


def texts(name: str) -> List[Tuple[str, str]]:
    return [(rel, read_text(rel)) for rel in card(name).get("prompt_files", [])]


def all_text_files() -> List[str]:
    return sorted(str(p.relative_to(METHODS_DIR)) for p in METHODS_DIR.rglob("*.txt") if "__pycache__" not in p.parts)


__all__ = ["METHODS_DIR", "ORDER", "read_text", "prompt_hash", "cards", "card", "texts", "all_text_files"]
