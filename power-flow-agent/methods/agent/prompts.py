"""methods/agent/prompts.py

System prompt & prompt templates.

本项目刻意保持“单 LLM + 工具调用（Function Calling）”的简洁架构：
- LLM 只做意图解析、规划与自然语言解读
- 所有数值结果只能来自 solver 工具函数
"""

import hashlib

from methods import read_text as _read_method_text


def prompt_hash(text: str) -> str:
    """Short, stable identifier for a system prompt's exact text.

    Runs are attributable to a model, case and seed but not to the prompt they were given.
    Store this alongside every trace/row so a later prompt-wording change (like the
    2026-09-17 bus-indexing fix) doesn't silently make two runs of the "same" method
    incomparable.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


SYSTEM_PROMPT = _read_method_text("_shared/agent_system_prompt_zh_ui.txt")


# English system prompt used by the benchmark harness (revision R1). Same rules as SYSTEM_PROMPT,
# without the UI-only visualization instructions, and with the reply language fixed to English so
# that traceability metrics and trace analysis are language-independent.
SYSTEM_PROMPT_EN = _read_method_text("_shared/agent_system_prompt.txt")
