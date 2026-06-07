# Explanation faithfulness: auto-verify claims vs computed schedule statistics; §5.

from evaluation.faithfulness.faithfulness import (
    ClaimCheck,
    FaithfulnessResult,
    check_faithfulness,
    check_faithfulness_facts,
    parse_explanation_for_facts,
)

__all__ = [
    "ClaimCheck",
    "FaithfulnessResult",
    "check_faithfulness",
    "check_faithfulness_facts",
    "parse_explanation_for_facts",
]
