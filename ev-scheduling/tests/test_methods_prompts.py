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
    "_shared/agent_output_contract.txt": "f39d049df51bd88bd39193b625d2f983b159dd4865272b9e379c3b9a5364311a",
    "_shared/agent_role.txt": "b342344bcbc8f997ef092adf9d8b105b88d2213b116000938bbd48dc389ffe40",
    "_shared/agent_system_prompt.txt": "37d182fa4fd939f5ccf2a80b1115e122c2f5feb023cca4da236b1c58cb3e4326",
    "_shared/answer_rule.txt": "d79d01ab98691423410fda80c1401ea3eb26430c21ecdf5e16b513e89ac05d09",
    "_shared/llm_only_output_contract.txt": "348e921ffde4e02114996385116b6325a1860daf2719776a9813af73afcb4f05",
    "_shared/llm_only_role.txt": "a4b5ca74dfbc00f047605340a40cc9d9e66d8a7b980bafb72b6169dafe17fea4",
    "_shared/llm_only_system_prompt.txt": "b10e66600ef56ea50f7f24a4259bd811ef61a41d7d0213f6dc971f1a411d978a",
    "_shared/parse_extraction_system.txt": "c6d0f98682f0d0ecab579952259072c0e757a8d291b4990e629f262eb741c458",
    "_shared/parse_inference_system.txt": "8d326d4f23a4b5a3477a02a3781ce48d26c65ffa4b4246cc3474afbf024b495e",
    "llm_only_cot/reasoning_section.txt": "9e800ca719659a45c33d92e4dfa768675e7f2a0f4d119c2d095137aa5867e486",
    "llm_only_cot/system_suffix.txt": "c18c3e486ff6beca491961ee4af90bd1f3512e56b8b46788579a35fbea6c0709",
    "llm_only_structured/system_suffix.txt": "7914b0e72bd9517221342aa49d08b17b59393528b54e90c0d7c52a4d4b912063",
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
    # and the answer contract is the one file, shared
    assert "_shared/llm_only_output_contract.txt" in structured & cot


def test_the_agent_methods_share_one_system_prompt() -> None:
    """Plan-and-Act, ReAct and EVAgent differ by architecture, not by wording.

    Plan-and-Act adds its planner text on top; every other text is the same.
    """
    shared = {
        "_shared/agent_system_prompt.txt",
        "_shared/agent_role.txt",
        "_shared/agent_output_contract.txt",
        "_shared/answer_rule.txt",
        "_shared/parse_extraction_system.txt",
        "_shared/parse_inference_system.txt",
    }
    for name in ("plan_act_nogate", "react_nogate", "evagent"):
        assert shared <= set(methods.prompt_files(name))
    assert set(methods.prompt_files("plan_act_nogate")) - shared == {
        "plan_act_nogate/plan_system_prompt.txt"
    }
    assert set(methods.prompt_files("react_nogate")) == set(methods.prompt_files("evagent"))


def test_every_method_that_answers_is_held_to_one_answer_rule() -> None:
    """The rule about what the answer must say is one file, used by all five.

    Five of the six rows send a prompt; the sixth has none. If a row could be
    held to a different rule about what counts as answering the question, the
    answer term of Solved would not be one measurement, and the table's rows
    would not be comparable on it.
    """
    rule = "_shared/answer_rule.txt"
    for name in ("llm_only_structured", "llm_only_cot", "plan_act_nogate", "react_nogate", "evagent"):
        assert rule in methods.prompt_files(name), name
    assert rule not in methods.prompt_files("rule_based")


def test_the_parse_prompt_states_no_value_of_its_own() -> None:
    """The extraction prompt must not supply the benchmark's own numbers.

    It used to give 50.0 kW, 0.45 and 0.12 $/kWh with the 4pm-9pm window, and
    7.0 kW per plug, as defaults. Eighteen of the twenty frozen days state a
    50 kW cap and all twenty state those two prices, so a model that never read
    those sentences would have got them right anyway, and Formulation would have
    been measuring the prompt. Every field is null in the schema now.
    """
    text = methods.read_text("_shared/parse_extraction_system.txt")
    for crib in ("50.0", "0.45", "0.12", "7.0 (Level 2", "default 7.0"):
        assert crib not in text, f"the parse prompt supplies {crib!r}"
    assert "do not supply one from what is usual" in text


def test_read_text_keeps_leading_whitespace() -> None:
    """Two texts are appended to a sentence and begin with a space."""
    for relative in ("llm_only_structured/system_suffix.txt", "llm_only_cot/system_suffix.txt"):
        assert methods.read_text(relative).startswith(" ")
