"""Pin every prompt text under methods/ to its hash.

If a test here fails, a prompt changed. That is allowed, but it makes new runs
incomparable with the committed ones, so update the pinned value here on
purpose, in the same commit, and say so in the commit message.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import methods  # noqa: E402

# Recorded 2026-09-27 when the texts were written. Updated on purpose 2026-09-28: the answer
# contract now tells the model that the actions it lists are checked against the trace (gate G7).
# The smoke run of 2026-09-27 was made with the previous contract; no paper run exists yet.
PINNED_TEXTS = {
    "_shared/agent_system_prompt.txt": "55f4e3c29cdd",
    "_shared/common_rules.txt": "8c0f85ea1170",
    "_shared/gate_retry_instruction.txt": "81e0764be9cb",
    "_shared/llm_only_system_prompt.txt": "687705944e54",
    "_shared/output_contract.txt": "32ab6c8f3a3d",
    "llm_only_cot/reasoning_section.txt": "e6b046ab723e",
    "plan_act_nogate/plan_system_prompt.txt": "a08bfb652562",
}


def test_every_text_file_is_pinned():
    assert sorted(methods.all_text_files()) == sorted(PINNED_TEXTS), "a prompt file was added or removed; update PINNED_TEXTS"


@pytest.mark.parametrize("rel", sorted(PINNED_TEXTS))
def test_text_hash_is_pinned(rel):
    assert methods.prompt_hash(methods.read_text(rel)) == PINNED_TEXTS[rel], f"{rel} changed; update the pin on purpose"


def test_every_method_lists_existing_files():
    for c in methods.cards():
        for rel in c.get("prompt_files", []):
            assert (methods.METHODS_DIR / rel).is_file(), (c["folder"], rel)


def test_six_methods_in_order():
    assert [c["folder"] for c in methods.cards()] == list(methods.ORDER)
