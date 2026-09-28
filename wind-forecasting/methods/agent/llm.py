"""One place where a model is called, so no call escapes the token and latency accounting.

``Recorder`` keeps the audit trail of one run: every model call with its
usage, content and requested tool calls, every tool call with its output, the
full message transcript and the final answer. ``call_chat`` is the single
function that talks to the SDK. The trace it produces has the field names of
the power-flow traces (``rounds``, ``n_llm_calls``, ``n_tool_calls``,
``prompt_tokens``, ``completion_tokens``, ``wall_time_s``, ``answer``).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import ModelSpec


def to_jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            return to_jsonable(obj.model_dump(exclude_none=True))
        except Exception:
            pass
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    if hasattr(obj, "tolist"):
        try:
            return to_jsonable(obj.tolist())
        except Exception:
            pass
    return str(obj)


def _usage(resp: Any) -> Dict[str, Optional[int]]:
    u = getattr(resp, "usage", None)
    if u is None and isinstance(resp, dict):
        u = resp.get("usage")

    def rd(name: str) -> Optional[int]:
        if u is None:
            return None
        v = u.get(name) if isinstance(u, dict) else getattr(u, name, None)
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    p, c, t = rd("prompt_tokens"), rd("completion_tokens"), rd("total_tokens")
    if t is None and (p is not None or c is not None):
        t = int(p or 0) + int(c or 0)
    return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": t}


@dataclass
class Recorder:
    spec: ModelSpec
    method: str
    request_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    n_llm_calls: int = 0
    n_tool_calls: int = 0
    n_missing_usage: int = 0
    rounds: List[Dict[str, Any]] = field(default_factory=list)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    answer_text: str = ""
    status: str = "ok"
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    extra: Dict[str, Any] = field(default_factory=dict)

    def record_llm(self, resp: Any, latency_s: float, *, with_tools: bool, role: str = "assistant") -> Dict[str, Any]:
        self.n_llm_calls += 1
        u = _usage(resp)
        if u["prompt_tokens"] is None and u["total_tokens"] is None:
            self.n_missing_usage += 1
        self.prompt_tokens += int(u["prompt_tokens"] or 0)
        self.completion_tokens += int(u["completion_tokens"] or 0)
        msg = None
        choices = getattr(resp, "choices", None) or (resp.get("choices") if isinstance(resp, dict) else None)
        if choices:
            first = choices[0]
            msg = getattr(first, "message", None) or (first.get("message") if isinstance(first, dict) else None)
        content, calls = None, []
        finish = None
        if choices:
            first = choices[0]
            finish = getattr(first, "finish_reason", None) if not isinstance(first, dict) else first.get("finish_reason")
        if msg is not None:
            content = getattr(msg, "content", None) if not isinstance(msg, dict) else msg.get("content")
            raw = getattr(msg, "tool_calls", None) if not isinstance(msg, dict) else msg.get("tool_calls")
            for tc in raw or []:
                fn = getattr(tc, "function", None) if not isinstance(tc, dict) else tc.get("function", {})
                calls.append({
                    "id": getattr(tc, "id", None) if not isinstance(tc, dict) else tc.get("id"),
                    "name": getattr(fn, "name", None) if not isinstance(fn, dict) else fn.get("name"),
                    "arguments": getattr(fn, "arguments", "{}") if not isinstance(fn, dict) else fn.get("arguments", "{}"),
                })
        entry = {"round": len(self.rounds) + 1, "role": role,
                 "llm": {"content": content, "tool_calls": calls, "usage": u, "with_tools": bool(with_tools), "latency_s": round(float(latency_s), 4),
                         "finish_reason": finish},
                 "tools": []}
        self.rounds.append(entry)
        return entry

    def record_tool(self, entry: Dict[str, Any]) -> None:
        """Attach a dispatcher log entry to the current round."""
        self.n_tool_calls += 1
        if not self.rounds:
            self.rounds.append({"round": 1, "role": "harness", "llm": None, "tools": []})
        self.rounds[-1]["tools"].append(to_jsonable(entry))

    @property
    def truncated(self) -> bool:
        """Whether any model call stopped at the token cap (finish_reason length)."""
        return any((r.get("llm") or {}).get("finish_reason") == "length" for r in self.rounds)

    def finish(self, *, messages: Optional[List[Dict[str, Any]]] = None, answer_text: str = "", status: str = "ok", error: Optional[str] = None) -> None:
        self.wall_time_s = round(time.time() - self.started_at, 4)
        if messages is not None:
            self.messages = [to_jsonable(m) for m in messages]
        self.answer_text = answer_text or ""
        self.status, self.error = status, error

    def to_dict(self) -> Dict[str, Any]:
        wall = getattr(self, "wall_time_s", round(time.time() - self.started_at, 4))
        return {
            "case_study": "wind",
            "method": self.method,
            "model": self.spec.key,
            "request_id": self.request_id,
            "status": self.status,
            "error": self.error,
            "answer": self.answer_text,
            "messages": self.messages,
            "rounds": self.rounds,
            "n_llm_calls": self.n_llm_calls,
            "n_tool_calls": self.n_tool_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "n_missing_usage": self.n_missing_usage,
            "truncated": self.truncated,
            "wall_time_s": wall,
            **self.extra,
        }


def call_chat(client: Any, recorder: Optional[Recorder], *, with_tools: bool = False, **kwargs: Any) -> Any:
    t0 = time.time()
    resp = client.chat.completions.create(**kwargs)
    if recorder is not None:
        recorder.record_llm(resp, time.time() - t0, with_tools=with_tools)
    return resp


def message_of(resp: Any) -> Any:
    return resp.choices[0].message


def tool_calls_of(msg: Any) -> List[Dict[str, Any]]:
    out = []
    for tc in getattr(msg, "tool_calls", None) or []:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {"_unparsed": tc.function.arguments}
        out.append({"id": tc.id, "name": tc.function.name, "args": args if isinstance(args, dict) else {"_value": args}})
    return out
