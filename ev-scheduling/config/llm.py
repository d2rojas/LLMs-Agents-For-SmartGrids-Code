"""Shared LLM client, model selection, and cost instrumentation.

Both entry points that talk to a model (``baseline.run.run_baseline`` and
``agent.llm_agent.run_agent_llm``) get their client from here, so provider
resolution, token accounting, and trace writing are defined once.

Provider
--------
The default path is OpenRouter, which exposes OpenAI, Anthropic, and Google
models behind one OpenAI-compatible API. This mirrors the power-flow case study
(``power-flow-agent/benchmarks/evaluate_llms.py``): model ids are written
``provider:model`` and the OpenRouter model carries a vendor prefix, e.g.

    openrouter:openai/gpt-4o
    openrouter:anthropic/claude-sonnet-4
    openai:gpt-4o                      (direct OpenAI, needs OPENAI_API_KEY)

A bare id such as ``gpt-4o`` is accepted for backward compatibility: it is
resolved to the default provider, and the ``openai/`` vendor prefix is added
when that provider is OpenRouter. Keys are ``OPENROUTER_API_KEY`` and
``OPENAI_API_KEY``; OpenRouter wins when both are present.

Instrumentation
---------------
``RunUsage`` accumulates prompt, completion, and total tokens, the number of
model calls, the number of tool calls, and wall-clock seconds for one run (one
day for the paper's benchmark). ``RunRecorder`` adds the audit trail: the full
message transcript, every tool call with its arguments and its returned JSON,
and the final answer text. ``RunRecorder.write()`` stores that as one JSON file
per run, with the same field names the power-flow traces use, so the two case
studies produce comparable artefacts.
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Environment (.env discovery, no override of the process environment)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_PROVIDER = "openrouter"
DEFAULT_VENDOR = "openai"
DEFAULT_MODEL_SPEC = "openrouter:openai/gpt-4o"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TIMEOUT_S = 120.0

# Lowest priority first. The power-flow project holds the shared OpenRouter key;
# reading it here keeps one key for the whole repo instead of a second copy.
_ENV_FILES = (
    REPO_ROOT / "power-flow-agent" / ".env",
    REPO_ROOT / "power-flow-agent" / ".env.local",
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / ".env.local",
)


def _strip_wrapping_quotes(value: str) -> str:
    """Remove one layer of matching single or double quotes from a value."""
    v = value.strip()
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        return v[1:-1]
    return v


def _parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a KEY=VALUE .env file, ignoring blanks and comments."""
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            out[key] = _strip_wrapping_quotes(value)
    return out


def load_env_defaults() -> None:
    """Load .env defaults into os.environ without overriding what is already set.

    Searched in increasing priority: the power-flow project's .env (shared
    OpenRouter key), then this project's .env and .env.local. Real environment
    variables always win.
    """
    merged: Dict[str, str] = {}
    for path in _ENV_FILES:
        merged.update(_parse_env_file(path))
    for k, v in merged.items():
        if k not in os.environ:
            os.environ[k] = v


load_env_defaults()


# ---------------------------------------------------------------------------
# Model and provider resolution
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelSpec:
    """A provider plus a model id, as written ``provider:model``.

    Attributes:
        provider: "openrouter" or "openai".
        model: Model id as the provider expects it. OpenRouter ids carry a
            vendor prefix (``openai/gpt-4o``); direct OpenAI ids do not.
    """

    provider: str
    model: str

    @property
    def key(self) -> str:
        """Canonical ``provider:model`` string."""
        return f"{self.provider}:{self.model}"

    @property
    def slug(self) -> str:
        """Filesystem-safe form of ``key``, for trace file and directory names."""
        return self.key.replace("/", "_").replace(":", "_").replace(".", "-")


def default_provider() -> str:
    """Return the provider to use when a model id carries no explicit one.

    OpenRouter is the default path. Direct OpenAI is used only when there is no
    OpenRouter key and an OPENAI_API_KEY is set.
    """
    if os.environ.get("OPENROUTER_API_KEY", "").strip():
        return "openrouter"
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return "openai"
    return DEFAULT_PROVIDER


def parse_model_spec(raw: Optional[str] = None) -> ModelSpec:
    """Resolve a model id string to a ModelSpec.

    Accepts ``provider:model`` (e.g. ``openrouter:anthropic/claude-sonnet-4``)
    or a bare model id (e.g. ``gpt-4o``), which is attached to
    ``default_provider()``. When the resolved provider is OpenRouter and the
    model has no vendor prefix, ``openai/`` is added. When the provider is
    direct OpenAI, a vendor prefix is stripped. A colon inside a vendor-prefixed
    id is an OpenRouter variant suffix (``anthropic/claude-sonnet-4:beta``), not
    a provider, and is left on the model.

    Args:
        raw: Model id, or None to use EV_LLM_MODEL, else DEFAULT_MODEL_SPEC.

    Returns:
        The resolved ModelSpec.

    Raises:
        ValueError: If the provider is not supported or the model is empty.
    """
    text = (raw or os.environ.get("EV_LLM_MODEL") or DEFAULT_MODEL_SPEC).strip()
    provider, sep, model = text.partition(":")
    if sep and "/" in provider:
        # A vendor-prefixed id with a variant suffix; the colon is not a provider.
        provider, sep, model = "", "", text
    if sep:
        provider = provider.strip().lower()
        model = model.strip()
    else:
        provider = default_provider()
        model = text

    if not model:
        raise ValueError(f"Invalid model spec: {raw!r}. Expected provider:model.")
    if provider not in ("openrouter", "openai"):
        raise ValueError(
            f"Unsupported provider: {provider}. Use 'openrouter' or 'openai'."
        )

    if provider == "openrouter" and "/" not in model:
        model = f"{DEFAULT_VENDOR}/{model}"
    if provider == "openai" and model.startswith(f"{DEFAULT_VENDOR}/"):
        model = model.split("/", 1)[1]

    return ModelSpec(provider=provider, model=model)


def resolve_api_key(provider: str) -> str:
    """Return the API key for a provider, or an empty string if it is not set."""
    p = str(provider).strip().lower()
    if p == "openrouter":
        return str(os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if p == "openai":
        return str(os.environ.get("OPENAI_API_KEY") or "").strip()
    raise ValueError(f"Unsupported provider: {provider}")


def resolve_base_url(provider: str) -> Optional[str]:
    """Return the OpenAI-compatible base URL for a provider (None for OpenAI)."""
    p = str(provider).strip().lower()
    if p == "openrouter":
        return os.environ.get("OPENROUTER_BASE_URL") or OPENROUTER_BASE_URL
    return None


def missing_key_message(spec: ModelSpec) -> str:
    """Return the error text used when the provider's key is absent."""
    if spec.provider == "openrouter":
        return (
            "OPENROUTER_API_KEY is not set; cannot call the model "
            f"{spec.key}. Put it in ev-scheduling/.env (or export it), or set "
            "OPENAI_API_KEY and pass an openai:<model> id to use OpenAI directly."
        )
    return (
        f"OPENAI_API_KEY is not set; cannot call the model {spec.key}. "
        "Put it in ev-scheduling/.env or use an openrouter:<vendor>/<model> id."
    )


# A request that must emit a whole schedule can legitimately run for minutes: the
# no-tools arm writes up to 16k completion tokens, which is 3 to 5 minutes at the
# rates these models generate. The SDK's own default is 600 s with 2 retries, and
# a 20-day run left a request hanging with no output and no CPU for 14 minutes
# before it was killed by hand. These bound it: each attempt gets REQUEST_TIMEOUT_S
# and a stalled connection is retried rather than waited on. The power-flow case
# lost 77 minutes to the same failure and resolved it with an external watchdog.
REQUEST_TIMEOUT_S: float = float(os.environ.get("EV_REQUEST_TIMEOUT_S", "420"))
MAX_RETRIES: int = int(os.environ.get("EV_MAX_RETRIES", "3"))


def build_client(spec: ModelSpec, api_key: Optional[str] = None) -> Any:
    """Build an OpenAI-SDK client pointed at the provider named by ``spec``.

    Args:
        spec: Resolved model spec; only its provider is used here.
        api_key: Explicit key; falls back to the provider's environment key.

    Returns:
        An ``openai.OpenAI`` client. OpenRouter is reached through the same SDK
        with ``base_url`` set, exactly as in the power-flow benchmark runner.

    Raises:
        ValueError: If no key is available for the provider.
        ImportError: If the 'openai' package is not installed.
    """
    key = (api_key or resolve_api_key(spec.provider)).strip()
    if not key:
        raise ValueError(missing_key_message(spec))

    try:
        from openai import OpenAI  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "The 'openai' package is not installed. "
            "Install it with 'pip install openai>=1.0.0'."
        ) from exc

    return OpenAI(
        api_key=key,
        base_url=resolve_base_url(spec.provider),
        timeout=REQUEST_TIMEOUT_S,
        max_retries=MAX_RETRIES,
    )


# ---------------------------------------------------------------------------
# Cost instrumentation
# ---------------------------------------------------------------------------

@dataclass
class RunUsage:
    """Accumulated cost of one run (one day), across every model call.

    Attributes:
        prompt_tokens: Sum of prompt tokens reported by the provider.
        completion_tokens: Sum of completion tokens reported by the provider.
        total_tokens: Sum of total tokens; falls back to prompt + completion.
        n_llm_calls: Number of model calls issued.
        n_tool_calls: Number of tool calls executed.
        wall_time_s: Wall-clock seconds for the whole run.

    Verifications:
        Providers may omit usage on a response. Missing fields add zero and are
        counted in ``n_missing_usage`` so a run with unknown tokens is visible
        rather than silently reported as cheap.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    n_llm_calls: int = 0
    n_tool_calls: int = 0
    wall_time_s: float = 0.0
    n_missing_usage: int = 0

    def add_response(self, response: Any) -> Dict[str, Optional[int]]:
        """Add one model response to the totals and return its token counts.

        Args:
            response: A chat-completions response object or dict.

        Returns:
            Dict with prompt_tokens, completion_tokens, total_tokens for this
            single call; values are None when the provider reported none.
        """
        self.n_llm_calls += 1
        counts = extract_token_counts(response)
        if counts["total_tokens"] is None and counts["prompt_tokens"] is None:
            self.n_missing_usage += 1
        self.prompt_tokens += int(counts["prompt_tokens"] or 0)
        self.completion_tokens += int(counts["completion_tokens"] or 0)
        self.total_tokens += int(counts["total_tokens"] or 0)
        return counts

    def add_tool_call(self, n: int = 1) -> None:
        """Count ``n`` executed tool calls."""
        self.n_tool_calls += int(n)

    def as_dict(self) -> Dict[str, Any]:
        """Return the totals as a JSON-serialisable dict."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "n_llm_calls": self.n_llm_calls,
            "n_tool_calls": self.n_tool_calls,
            "wall_time_s": round(self.wall_time_s, 4),
            "n_missing_usage": self.n_missing_usage,
        }


def extract_token_counts(response: Any) -> Dict[str, Optional[int]]:
    """Read prompt, completion, and total tokens off a response.

    Works for SDK objects and plain dicts. ``total_tokens`` is derived from the
    other two when the provider does not send it.

    Args:
        response: A chat-completions response object or dict.

    Returns:
        Dict with keys prompt_tokens, completion_tokens, total_tokens; each is
        an int, or None when unavailable.
    """
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}

    def _read(name: str) -> Optional[int]:
        val = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        try:
            return int(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    prompt = _read("prompt_tokens")
    completion = _read("completion_tokens")
    total = _read("total_tokens")
    if total is None and (prompt is not None or completion is not None):
        total = int(prompt or 0) + int(completion or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def to_jsonable(obj: Any) -> Any:
    """Convert SDK objects, dataclasses, and arrays to JSON-serialisable data."""
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


# ---------------------------------------------------------------------------
# Run recorder (usage + audit trail + trace file)
# ---------------------------------------------------------------------------

def default_trace_dir() -> Path:
    """Return the directory traces are written to.

    ``EV_TRACE_DIR`` overrides the default ``ev-scheduling/results/traces``.
    """
    raw = os.environ.get("EV_TRACE_DIR", "").strip()
    return Path(raw) if raw else PROJECT_ROOT / "results" / "traces"


@dataclass
class RunRecorder:
    """Collects usage and the audit trail of one run, then writes its trace.

    One recorder covers one day's run of one arm. It times the run from
    construction to ``finish()``, accumulates token counts over every model
    call, and keeps the material needed to audit a reported number: the full
    message transcript, each tool call with arguments and returned JSON, and
    the final answer text.

    Attributes:
        spec: Model spec used for the run.
        arm: "agent" or "baseline"; becomes the trace sub-directory.
        run_id: Identifier for this run, normally the day (e.g. "2019-06-15").
        request: Natural-language request sent to the model, if any.
        usage: Accumulated RunUsage.
        rounds: Per-round record of model calls and the tool calls they caused.
        messages: Full message transcript as sent to and returned by the model.
        final_text: Final answer text (explanation, or the baseline's raw reply).
        status: "ok" or a short failure label.
        error: Error text when status is not "ok".
    """

    spec: ModelSpec
    arm: str
    run_id: str = ""
    request: Optional[str] = None
    usage: RunUsage = field(default_factory=RunUsage)
    rounds: List[Dict[str, Any]] = field(default_factory=list)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    final_text: str = ""
    status: str = "ok"
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")

    # -- recording ---------------------------------------------------------

    def record_llm_call(
        self,
        response: Any,
        latency_s: float,
        *,
        with_tools: bool = False,
    ) -> Dict[str, Any]:
        """Record one model response: usage, content, and requested tool calls.

        Args:
            response: The chat-completions response.
            latency_s: Seconds this single call took.
            with_tools: True if the call offered tools to the model.

        Returns:
            The round dict that was appended to ``rounds``.
        """
        counts = self.usage.add_response(response)
        message = None
        choices = getattr(response, "choices", None)
        if choices is None and isinstance(response, dict):
            choices = response.get("choices")
        if choices:
            first = choices[0]
            message = getattr(first, "message", None)
            if message is None and isinstance(first, dict):
                message = first.get("message")

        content = None
        tool_calls: List[Dict[str, Any]] = []
        if message is not None:
            content = getattr(message, "content", None)
            if content is None and isinstance(message, dict):
                content = message.get("content")
            raw_calls = getattr(message, "tool_calls", None)
            if raw_calls is None and isinstance(message, dict):
                raw_calls = message.get("tool_calls")
            for tc in raw_calls or []:
                fn = getattr(tc, "function", None)
                if fn is None and isinstance(tc, dict):
                    fn = tc.get("function", {})
                tool_calls.append(
                    {
                        "id": getattr(tc, "id", None) if not isinstance(tc, dict) else tc.get("id"),
                        "name": (
                            getattr(fn, "name", None)
                            if not isinstance(fn, dict)
                            else fn.get("name")
                        ),
                        "arguments": (
                            getattr(fn, "arguments", "{}")
                            if not isinstance(fn, dict)
                            else fn.get("arguments", "{}")
                        ),
                    }
                )

        entry: Dict[str, Any] = {
            "round": len(self.rounds) + 1,
            "llm": {
                "content": content,
                "tool_calls": tool_calls,
                "usage": counts,
                "with_tools": bool(with_tools),
                "latency_s": float(latency_s),
            },
            "tools": [],
        }
        self.rounds.append(entry)
        return entry

    def record_tool_call(
        self,
        *,
        call_id: Optional[str],
        name: str,
        arguments: Any,
        output: Any,
        latency_s: float,
    ) -> None:
        """Record one executed tool call with its arguments and returned JSON.

        Attached to the most recent model call so the trace keeps the
        think-act order. Counts towards ``usage.n_tool_calls``.
        """
        self.usage.add_tool_call()
        output_json = output if isinstance(output, str) else json.dumps(to_jsonable(output))
        record = {
            "id": call_id,
            "name": name,
            "arguments": to_jsonable(arguments),
            "output": output_json,
            "output_chars": len(output_json),
            "latency_s": float(latency_s),
        }
        if not self.rounds:
            self.rounds.append({"round": 1, "llm": None, "tools": []})
        self.rounds[-1]["tools"].append(record)

    def finish(
        self,
        *,
        messages: Optional[List[Dict[str, Any]]] = None,
        final_text: str = "",
        status: str = "ok",
        error: Optional[str] = None,
    ) -> RunUsage:
        """Close the run: stop the clock and store the transcript and answer.

        Args:
            messages: Full message transcript of the run.
            final_text: Final answer text.
            status: "ok", or a short failure label.
            error: Error text when the run failed.

        Returns:
            The accumulated RunUsage, with wall_time_s set.
        """
        self.usage.wall_time_s = float(time.time() - self.started_at)
        if messages is not None:
            self.messages = [to_jsonable(m) for m in messages]
        self.final_text = final_text or ""
        self.status = status
        self.error = error
        return self.usage

    # -- serialisation -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return the whole trace as a JSON-serialisable dict.

        Field names follow the power-flow traces (``model``, ``rounds``,
        ``answer``, ``n_llm_calls``, ``n_tool_calls``, ``prompt_tokens``,
        ``completion_tokens``, ``wall_time_s``) so both case studies can be read
        by the same tooling.
        """
        usage = self.usage.as_dict()
        return {
            "case_study": "ev_scheduling",
            "arm": self.arm,
            "model": self.spec.key,
            "provider": self.spec.provider,
            "run_id": self.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "request": self.request,
            "status": self.status,
            "error": self.error,
            "answer": self.final_text,
            "messages": self.messages,
            "trace": {
                "rounds": self.rounds,
                "final_text": self.final_text,
                **usage,
            },
            "usage": usage,
        }

    def write(self, trace_dir: Optional[Path] = None) -> Path:
        """Write the trace as one JSON file and return its path.

        The layout mirrors the power-flow runner's ``traces/<method>/<case>/``:
        here it is ``<trace_dir>/<arm>/<model slug>/<run_id>.json``.

        Args:
            trace_dir: Root directory; defaults to ``default_trace_dir()``.

        Returns:
            Path of the written file.
        """
        root = Path(trace_dir) if trace_dir is not None else default_trace_dir()
        out_dir = root / self.arm / self.spec.slug
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{self.run_id}.json"
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return path


def call_chat(
    client: Any,
    recorder: Optional[RunRecorder],
    *,
    with_tools: bool = False,
    **kwargs: Any,
) -> Any:
    """Issue one chat-completions call, timed and recorded.

    This is the single place a model call is made, so no call can escape the
    token and latency accounting.

    Args:
        client: Object exposing ``chat.completions.create``.
        recorder: RunRecorder to update, or None to skip recording.
        with_tools: True if the call offers tools to the model.
        **kwargs: Passed straight to the SDK (model, messages, temperature, ...).

    Returns:
        The provider's response object.
    """
    t0 = time.time()
    response = client.chat.completions.create(**kwargs)
    latency_s = time.time() - t0
    if recorder is not None:
        recorder.record_llm_call(response, latency_s, with_tools=with_tools)
    return response
