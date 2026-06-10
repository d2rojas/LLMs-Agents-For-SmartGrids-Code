"""llm/engine.py

LLM 调用核心引擎（意图解析 + Function Calling）。

目标（与 PRD 一致）：
- 单 LLM + tools（不引入 multi-agent / LangChain / LangGraph）
- 支持多轮 tool calling（一次用户输入可连续调用多个工具）
- 完整错误处理：API 失败、tool 失败、参数 JSON 解析失败等
- 会话历史管理：保留最近 N 条消息（默认约 20 轮对话）

本模块对 Streamlit 无依赖：
- 上层（app.py）可以把 st.session_state.session 传入这里
- tool 的执行通过 ToolDispatcher 注入
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from models.schemas import SessionState
from llm.prompts import SYSTEM_PROMPT
from llm.tools import ToolDispatcher, get_openai_tools


@dataclass(frozen=True)
class EngineConfig:
    """LLM 引擎配置。"""

    model: str = "gpt-4o-mini"  # 默认值仅作为占位；实际运行可由 config.py/环境变量覆盖
    temperature: float = 0.2
    max_tool_rounds: int = 8
    max_history_messages: int = 40  # 约等于 20 轮（user+assistant）
    timeout_s: float = 60.0


class LLMClient:
    """一个最小客户端接口：只要实现 create(...) 即可。

    生产环境可使用 OpenAI SDK 的适配器；测试环境可用 FakeClient。
    """

    def create(self, **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError


class OpenAIChatClient(LLMClient):
    """OpenAI Python SDK v1 适配器。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def create(self, **kwargs: Any) -> Any:
        return self._client.chat.completions.create(**kwargs)


def _trim_history(history: List[Dict[str, Any]], max_messages: int) -> List[Dict[str, Any]]:
    """保留最后 max_messages 条消息（不包含 system prompt）。"""
    if max_messages <= 0:
        return []
    if len(history) <= max_messages:
        return history
    return history[-max_messages:]


def _safe_json_loads(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s or "{}")
    except Exception:
        # OpenAI 有时会返回非严格 JSON（例如多余空格/换行仍 OK；但若真坏了就兜底）
        return {}


def _normalize_tool_calls(tool_calls: Any) -> List[Dict[str, Any]]:
    """把 tool_calls 规范化为 [{id,name,arguments}] 列表。"""
    if not tool_calls:
        return []

    norm: List[Dict[str, Any]] = []
    for tc in tool_calls:
        # SDK object
        if hasattr(tc, "id") and hasattr(tc, "function"):
            fn = tc.function
            norm.append(
                {
                    "id": getattr(tc, "id"),
                    "name": getattr(fn, "name", None),
                    "arguments": getattr(fn, "arguments", "{}"),
                }
            )
            continue

        # dict
        if isinstance(tc, dict):
            fn = tc.get("function", {})
            norm.append(
                {
                    "id": tc.get("id"),
                    "name": fn.get("name"),
                    "arguments": fn.get("arguments", "{}"),
                }
            )
            continue

    return norm


def _extract_choice_message(resp: Any) -> Dict[str, Any]:
    """从 OpenAI 响应中提取第一条 message，并转为 dict。"""
    # dict response
    if isinstance(resp, dict):
        msg = resp["choices"][0]["message"]
        return {
            "role": msg.get("role", "assistant"),
            "content": msg.get("content"),
            "tool_calls": _normalize_tool_calls(msg.get("tool_calls")),
        }

    # SDK response
    msg = resp.choices[0].message
    return {
        "role": getattr(msg, "role", "assistant"),
        "content": getattr(msg, "content", None),
        "tool_calls": _normalize_tool_calls(getattr(msg, "tool_calls", None)),
    }


class LLMEngine:
    """单模型工具调用引擎。"""

    def __init__(
        self,
        client: LLMClient,
        dispatcher: ToolDispatcher,
        *,
        system_prompt: str = SYSTEM_PROMPT,
        config: EngineConfig = EngineConfig(),
    ):
        self.client = client
        self.dispatcher = dispatcher
        self.system_prompt = system_prompt
        self.config = config
        self._openai_tools = get_openai_tools()

    def run(self, user_message: str, session: SessionState) -> str:
        """处理一次用户输入，返回最终 assistant 文本。"""

        if session.conversation_history is None:
            session.conversation_history = []

        session.conversation_history = _trim_history(
            list(session.conversation_history), self.config.max_history_messages
        )

        # 组装 messages
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        messages.extend(session.conversation_history)
        messages.append({"role": "user", "content": user_message})

        # 在 session 中记录 user
        session.conversation_history.append({"role": "user", "content": user_message})

        tool_round = 0
        while True:
            if tool_round >= self.config.max_tool_rounds:
                final_text = "工具调用轮次超过上限。请缩小问题范围或减少连续操作。"
                session.conversation_history.append({"role": "assistant", "content": final_text})
                return final_text

            try:
                resp = self.client.create(
                    model=self.config.model,
                    messages=messages,
                    tools=self._openai_tools,
                    tool_choice="auto",
                    temperature=self.config.temperature,
                    timeout=self.config.timeout_s,
                )
            except Exception as e:
                err_text = f"LLM request failed: {type(e).__name__}: {e}"
                session.conversation_history.append({"role": "assistant", "content": err_text})
                return err_text

            msg = _extract_choice_message(resp)
            assistant_entry: Dict[str, Any] = {
                "role": "assistant",
                "content": msg.get("content"),
            }
            # 若存在 tool_calls，需要把 tool_calls 也记录进 history（OpenAI 格式）
            if msg.get("tool_calls"):
                assistant_entry["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in msg["tool_calls"]
                ]

            session.conversation_history.append(assistant_entry)
            messages.append(assistant_entry)

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                final_text = (msg.get("content") or "").strip()
                return final_text

            # 执行工具
            for tc in tool_calls:
                tool_name = tc.get("name")
                args_str = tc.get("arguments", "{}")
                args = _safe_json_loads(args_str)

                tool_output = self.dispatcher.dispatch(tool_name, args)
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "name": tool_name,
                    "content": tool_output,
                }
                session.conversation_history.append(tool_msg)
                messages.append(tool_msg)

            tool_round += 1
