"""One folder per evaluated method, and the only copy of every prompt text.

Structure, following ``power-flow-agent/methods/``:

    methods/
      <method>/method.json     what the method is, and which texts it uses
      <method>/*.txt           the texts only that method uses
      _shared/*.txt            the texts several methods share

The modules that build prompts read these files at import time, so editing a
``.txt`` changes the prompt for the benchmark and for anything else that calls
the same builder. ``tests/test_methods_prompts.py`` pins the hash of every text
to the value the committed runs were produced with, which means changing a
prompt fails a test until the pin is updated deliberately. That is the point: a
silent wording change would make new runs incomparable with the ones already in
the paper, and nothing else in the pipeline would notice.

Whitespace in these files is significant. Two of them begin with a space
because they are appended to a sentence. ``read_text`` therefore strips exactly
one trailing newline, the one a text editor adds, and nothing else. Do not
reflow, re-indent or trim these files.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent

# The methods of the paper's table, in the order the table lists them. The same
# six names, in the same order, as every other case study.
ORDER: Tuple[str, ...] = (
    "rule_based",
    "llm_only_structured",
    "llm_only_cot",
    "plan_act_nogate",
    "react_nogate",
    "evagent",
)


@lru_cache(maxsize=None)
def read_text(relative: str) -> str:
    """One prompt text, verbatim but for the final newline.

    Args:
        relative: Path under ``methods/``, e.g. ``"_shared/llm_only_role.txt"``.

    Returns:
        The file's contents with exactly one trailing newline removed.

    Raises:
        FileNotFoundError: If the text does not exist. Prompts are not optional:
            a missing one is a broken install, not a reason to fall back.
    """
    text = (ROOT / relative).read_text(encoding="utf-8")
    return text[:-1] if text.endswith("\n") else text


@lru_cache(maxsize=None)
def card(name: str) -> Dict[str, Any]:
    """The ``method.json`` of one method.

    Args:
        name: Folder name, one of ``ORDER``.

    Returns:
        The parsed card.

    Raises:
        KeyError: If there is no such method.
    """
    path = ROOT / name / "method.json"
    if not path.exists():
        raise KeyError(f"unknown method {name!r}; known: {', '.join(ORDER)}")
    return json.loads(path.read_text(encoding="utf-8"))


def cards() -> List[Dict[str, Any]]:
    """Every method's card, in table order."""
    return [card(name) for name in ORDER]


def prompt_files(name: str) -> List[str]:
    """The texts one method is built from, shared ones included, in order."""
    return list(card(name).get("prompt_files", []))


def texts(name: str) -> List[Tuple[str, str]]:
    """(relative path, contents) for every text one method is built from."""
    return [(rel, read_text(rel)) for rel in prompt_files(name)]
