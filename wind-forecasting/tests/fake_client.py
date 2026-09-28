"""A scripted stand-in for the OpenAI client, so the model-backed methods run in tests without a key.

``FakeClient(script)`` answers each ``chat.completions.create`` call with the
next item of ``script``: a string (a plain assistant message) or a list of
``(tool_name, args)`` tuples (an assistant message with tool calls). The
objects it returns have the attributes the methods read: ``choices[0].message``
with ``content``, ``tool_calls`` (``id``, ``function.name``,
``function.arguments``) and ``model_dump``; and ``usage`` with token counts.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence, Tuple, Union

Step = Union[str, List[Tuple[str, Dict[str, Any]]]]


class _Fn:
    def __init__(self, name: str, args: Dict[str, Any]):
        self.name, self.arguments = name, json.dumps(args)


class _Call:
    def __init__(self, i: int, name: str, args: Dict[str, Any]):
        self.id, self.function, self.type = f"call_{i}", _Fn(name, args), "function"


class _Msg:
    def __init__(self, content: Any, calls: List[_Call]):
        self.role, self.content, self.tool_calls = "assistant", content, calls or None

    def model_dump(self, exclude_none: bool = True) -> Dict[str, Any]:
        d: Dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [{"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in self.tool_calls]
        return d


class _Choice:
    def __init__(self, msg: _Msg):
        self.message = msg


class _Usage:
    def __init__(self, p: int, c: int):
        self.prompt_tokens, self.completion_tokens, self.total_tokens = p, c, p + c


class _Resp:
    def __init__(self, msg: _Msg, p: int, c: int):
        self.choices, self.usage = [_Choice(msg)], _Usage(p, c)


class _Completions:
    def __init__(self, client: "FakeClient"):
        self._c = client

    def create(self, **kwargs: Any) -> _Resp:
        self._c.calls.append(kwargs)
        if not self._c.script:
            step: Step = json.dumps({"formulation": {}, "forecast": [], "source": None, "answer": None, "status": "cannot_forecast",
                                     "cannot_forecast": "script exhausted", "summary": "script exhausted"})
        else:
            step = self._c.script.pop(0)
        n = len(self._c.calls)
        if isinstance(step, str):
            msg = _Msg(step, [])
        else:
            msg = _Msg(None, [_Call(10 * n + i, name, args) for i, (name, args) in enumerate(step)])
        prompt = sum(len(str(m.get("content") or "")) for m in kwargs.get("messages", [])) // 4
        return _Resp(msg, prompt, 50)


class _Chat:
    def __init__(self, client: "FakeClient"):
        self.completions = _Completions(client)


class FakeClient:
    def __init__(self, script: Sequence[Step]):
        self.script: List[Step] = list(script)
        self.calls: List[Dict[str, Any]] = []
        self.chat = _Chat(self)


def answer_json(**over: Any) -> str:
    """A contract-shaped answer; ``series`` sets the forecast (default 18 zeros)."""
    series = over.pop("series", None)
    base = {
        "formulation": {"turbine": 8, "history_days": [201, 214], "horizon_hours": 3},
        "forecast": list(series) if series is not None else [0.0] * 18,
        "source": "gru_forecast",
        "answer": None,
        "status": "forecast",
        "cannot_forecast": None,
        "summary": "Forecast copied from gru_forecast for turbine 8, days 201 to 214, 3 h.",
    }
    base.update(over)
    return json.dumps(base)
