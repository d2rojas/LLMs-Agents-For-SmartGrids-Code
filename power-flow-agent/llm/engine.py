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


class AnthropicChatClient(LLMClient):
    """Anthropic Messages API adapter (official `anthropic` SDK).

    Accepts the same OpenAI-format kwargs the engine produces (messages,
    tools, tool_choice, temperature, timeout) and returns an OpenAI-shaped
    dict response, so LLMEngine works unchanged. Used for the Claude models
    reported in the paper (§VI-C: Claude Opus 4.7).
    """

    _DEFAULT_MAX_TOKENS = 8192

    def __init__(self, api_key: Optional[str] = None):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)

    @staticmethod
    def _convert_tools(openai_tools: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        tools = []
        for t in openai_tools or []:
            fn = t.get("function", {})
            tools.append(
                {
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return tools

    @staticmethod
    def _convert_messages(messages: List[Dict[str, Any]]) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """Split out the system prompt and convert OpenAI history to Anthropic blocks."""
        system: Optional[str] = None
        converted: List[Dict[str, Any]] = []

        for m in messages:
            role = m.get("role")
            if role == "system":
                system = m.get("content") or system
                continue

            if role == "assistant":
                blocks: List[Dict[str, Any]] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls") or []:
                    fn = tc.get("function", {})
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id"),
                            "name": fn.get("name"),
                            "input": _safe_json_loads(fn.get("arguments", "{}")),
                        }
                    )
                if blocks:
                    converted.append({"role": "assistant", "content": blocks})
                continue

            if role == "tool":
                result_block = {
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id"),
                    "content": m.get("content") or "",
                }
                # Anthropic expects tool results in a user turn; merge
                # consecutive tool messages into one user message.
                if converted and converted[-1]["role"] == "user" and isinstance(converted[-1]["content"], list):
                    converted[-1]["content"].append(result_block)
                else:
                    converted.append({"role": "user", "content": [result_block]})
                continue

            # plain user message
            converted.append({"role": "user", "content": m.get("content") or ""})

        return system, converted

    def create(self, **kwargs: Any) -> Any:
        system, messages = self._convert_messages(kwargs.get("messages") or [])

        request: Dict[str, Any] = {
            "model": kwargs["model"],
            "max_tokens": kwargs.get("max_tokens", self._DEFAULT_MAX_TOKENS),
            "messages": messages,
        }
        if system:
            request["system"] = system
        tools = self._convert_tools(kwargs.get("tools"))
        if tools:
            request["tools"] = tools
            request["tool_choice"] = {"type": "auto"}
        if kwargs.get("temperature") is not None:
            request["temperature"] = kwargs["temperature"]
        if kwargs.get("timeout") is not None:
            request["timeout"] = kwargs["timeout"]

        resp = self._client.messages.create(**request)

        # Re-shape to the OpenAI dict format _extract_choice_message understands.
        text = "".join(b.text for b in resp.content if b.type == "text") or None
        tool_calls = [
            {
                "id": b.id,
                "type": "function",
                "function": {"name": b.name, "arguments": json.dumps(b.input)},
            }
            for b in resp.content
            if b.type == "tool_use"
        ]
        message: Dict[str, Any] = {"role": "assistant", "content": text}
        if tool_calls:
            message["tool_calls"] = tool_calls
        usage = {
            "prompt_tokens": getattr(resp.usage, "input_tokens", None),
            "completion_tokens": getattr(resp.usage, "output_tokens", None),
        }
        return {"choices": [{"message": message}], "usage": usage}


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
