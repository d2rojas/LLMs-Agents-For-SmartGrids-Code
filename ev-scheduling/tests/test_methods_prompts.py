"""The prompts are pinned, so a wording change cannot happen by accident.

Every committed run was produced with the texts hashed below. A prompt that
changes without the pin changing would make new runs quietly incomparable with
the ones already reported, and nothing else in the pipeline would notice: the
scores would simply move. So the pin is the notice.

Changing a prompt on purpose means changing its hash here in the same commit,
and saying in the commit message which runs the change invalidates.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import methods

# sha256 of each text as ``methods.read_text`` returns it, i.e. with the final
# newline removed and nothing else touched.
PINS = {
    "_shared/agent_system_prompt.txt": "37d182fa4fd939f5ccf2a80b1115e122c2f5feb023cca4da236b1c58cb3e4326",
    "_shared/llm_only_role.txt": "a4b5ca74dfbc00f047605340a40cc9d9e66d8a7b980bafb72b6169dafe17fea4",
    "_shared/llm_only_system_prompt.txt": "a83b7b4f1f2aa5224ceee724daa42a5f1ff5c01dfbebe33dc76b0f1e799acae2",
    "_shared/parse_extraction_system.txt": "dfce05de41373d7e769727b24aa01f950ef37480f491a06b4ce2ef43e924e726",
    "_shared/parse_inference_system.txt": "8d326d4f23a4b5a3477a02a3781ce48d26c65ffa4b4246cc3474afbf024b495e",
    "llm_only_cot/reasoning_section.txt": "fe8fb883c579aac43672e2a4ea1f7cd4c57ce23826ea575a88f878c86247a3bf",
    "llm_only_cot/system_suffix.txt": "8c6fbcecf3995dc1092b9557d15e06be58e780d643d4988617a80130406d448a",
    "llm_only_structured/system_suffix.txt": "7d71bcffb2f6462613d2fa57bf831cbee439b40cc759a5483ffd306f93d1f0ba",
    "plan_act_nogate/plan_system_prompt.txt": "6a7627277fffda59a4932d39628646813572f2feb72686f2fe580c400de869bf",
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("relative", sorted(PINS))
def test_prompt_text_is_pinned(relative: str) -> None:
    assert sha(methods.read_text(relative)) == PINS[relative], (
        f"{relative} changed. If that was deliberate, update its hash in PINS in the same "
        "commit and say which runs the change invalidates."
    )


def test_every_text_is_pinned() -> None:
    """A new prompt file has to be pinned too, or it is unpinned in silence."""
    on_disk = {str(p.relative_to(methods.ROOT)) for p in methods.ROOT.rglob("*.txt")}
    assert on_disk == set(PINS), f"unpinned: {sorted(on_disk - set(PINS))}, stale: {sorted(set(PINS) - on_disk)}"


def test_every_method_has_a_card() -> None:
    for name in methods.ORDER:
        card = methods.card(name)
        assert card["folder"] == name
        assert card["description"].strip()


def test_cards_name_texts_that_exist() -> None:
    for name in methods.ORDER:
        for relative in methods.prompt_files(name):
            assert (methods.ROOT / relative).exists(), f"{name} names a missing text: {relative}"


def test_the_two_prompting_methods_differ_by_one_text() -> None:
    """The controlled comparison of the two prompting rows, as a test.

    They are a row apart in the paper's table on the claim that one prompt
    section separates them. If that stops being true the claim is wrong, and
    this is the only place that would catch it.
    """
    structured = set(methods.prompt_files("llm_only_structured"))
    cot = set(methods.prompt_files("llm_only_cot"))
    added = cot - structured
    removed = structured - cot
    assert added == {"llm_only_cot/reasoning_section.txt", "llm_only_cot/system_suffix.txt"}
    assert removed == {"llm_only_structured/system_suffix.txt"}


def test_the_agent_methods_share_one_system_prompt() -> None:
    """Plan-and-Act, ReAct and EVAgent differ by architecture, not by wording.

    Plan-and-Act adds its planner text on top; the answer turn uses the same
    system prompt as the other two.
    """
    shared = "_shared/agent_system_prompt.txt"
    for name in ("plan_act_nogate", "react_nogate", "evagent"):
        assert shared in methods.prompt_files(name)


def test_read_text_keeps_leading_whitespace() -> None:
    """Two texts are appended to a sentence and begin with a space."""
    for relative in ("llm_only_structured/system_suffix.txt", "llm_only_cot/system_suffix.txt"):
        assert methods.read_text(relative).startswith(" ")
