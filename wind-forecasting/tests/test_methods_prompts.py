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

# Recorded 2026-09-28, after the rated power moved out of the fixed rules and into the request and the
# tool outputs, where it belongs: it is a property of the machine, not a constant of the case study.
PINNED_TEXTS = {
    "_shared/agent_system_prompt.txt": "21795226f311",
    "_shared/common_rules.txt": "b19bc7e03cf7",
    "_shared/gate_retry_instruction.txt": "b4370d0298ed",
    "_shared/llm_only_system_prompt.txt": "873eff4d8734",
    "_shared/output_contract.txt": "ec148bd1af2d",
    "llm_only_cot/reasoning_section.txt": "15ceb870f33f",
    "plan_act_nogate/plan_system_prompt.txt": "a79112af0b70",
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
