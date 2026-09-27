"""Tests for config.llm and the instrumentation of both LLM entry points.

Every test runs offline: the client is a stub that returns canned responses, so
no API key is needed and no request is ever made.
"""

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pytest

from baseline.run import run_baseline
from config.llm import (
    ModelSpec,
    RunRecorder,
    RunUsage,
    build_client,
    call_chat,
    default_provider,
    extract_token_counts,
    parse_model_spec,
    resolve_api_key,
    resolve_base_url,
)
from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions, Session


_HAS_CVXPY = importlib.util.find_spec("cvxpy") is not None
requires_cvxpy = pytest.mark.skipif(not _HAS_CVXPY, reason="cvxpy is not installed")


# ---------------------------------------------------------------------------
# Stub client (mimics the shape of the OpenAI SDK objects we touch)
# ---------------------------------------------------------------------------

class _FakeFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.type = "function"
        self.function = _FakeFunction(name, arguments)

    def model_dump(self, exclude_none: bool = False) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "function": {"name": self.function.name, "arguments": self.function.arguments},
        }


class _FakeMessage:
    def __init__(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[_FakeToolCall]] = None,
    ) -> None:
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none: bool = False) -> Dict[str, Any]:
        out: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            out["tool_calls"] = [tc.model_dump(exclude_none) for tc in self.tool_calls]
        if exclude_none:
            out = {k: v for k, v in out.items() if v is not None}
        return out


class _FakeUsage:
    def __init__(self, prompt: Optional[int], completion: Optional[int], total: Optional[int]) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = total


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeResponse:
    def __init__(
        self,
        message: _FakeMessage,
        usage: Optional[_FakeUsage] = None,
    ) -> None:
        self.choices = [_FakeChoice(message)]
        self.usage = usage


class _FakeCompletions:
    def __init__(self, responses: List[_FakeResponse], calls: List[Dict[str, Any]]) -> None:
        self._responses = list(responses)
        self._calls = calls

    def create(self, **kwargs: Any) -> _FakeResponse:
        self._calls.append(kwargs)
        if not self._responses:
            raise AssertionError("The stub client ran out of scripted responses.")
        return self._responses.pop(0)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    """Stub with the one method the code calls: chat.completions.create."""

    def __init__(self, responses: List[_FakeResponse]) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.chat = _FakeChat(_FakeCompletions(responses, self.calls))


def _text_response(text: str, prompt: int = 100, completion: int = 20) -> _FakeResponse:
    return _FakeResponse(_FakeMessage(content=text), _FakeUsage(prompt, completion, prompt + completion))


def _tool_response(
    arguments: str = "{}",
    call_id: str = "call_1",
    prompt: int = 2000,
    completion: int = 30,
) -> _FakeResponse:
    message = _FakeMessage(
        content=None,
        tool_calls=[_FakeToolCall(call_id, "solve_ev_schedule", arguments)],
    )
    return _FakeResponse(message, _FakeUsage(prompt, completion, prompt + completion))


# ---------------------------------------------------------------------------
# Problem fixtures (small enough to solve in milliseconds)
# ---------------------------------------------------------------------------

@pytest.fixture
def tiny_problem() -> tuple[DaySessions, SiteConfig, TOUConfig]:
    """Two sessions over eight 15-minute steps."""
    n_steps = 8
    day = DaySessions(
        sessions=[
            Session(
                session_id="s0",
                arrival_idx=0,
                departure_idx=4,
                energy_kwh=3.0,
                charger_id="CA-1",
                max_power_kw=6.6,
            ),
            Session(
                session_id="s1",
                arrival_idx=2,
                departure_idx=8,
                energy_kwh=5.0,
                charger_id="CA-2",
                max_power_kw=6.6,
            ),
        ],
        n_steps=n_steps,
        dt_hours=0.25,
    )
    site = SiteConfig(P_max_kw=20.0, n_steps=n_steps, dt_hours=0.25)
    tou = TOUConfig(rates_per_kwh=np.full(n_steps, 0.1))
    return day, site, tou


# ---------------------------------------------------------------------------
# Model and provider resolution
# ---------------------------------------------------------------------------

def test_bare_model_id_goes_to_openrouter_with_vendor_prefix(monkeypatch) -> None:
    """A legacy id such as 'gpt-4o' resolves to openrouter:openai/gpt-4o."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("EV_LLM_MODEL", raising=False)
    spec = parse_model_spec("gpt-4o")
    assert spec == ModelSpec(provider="openrouter", model="openai/gpt-4o")
    assert spec.key == "openrouter:openai/gpt-4o"


def test_explicit_provider_is_honoured() -> None:
    """provider:model ids select the provider, power-flow style."""
    assert parse_model_spec("openai:gpt-4o") == ModelSpec("openai", "gpt-4o")
    assert parse_model_spec("openrouter:anthropic/claude-sonnet-4") == ModelSpec(
        "openrouter", "anthropic/claude-sonnet-4"
    )


def test_openai_provider_strips_vendor_prefix() -> None:
    """Direct OpenAI does not take the OpenRouter vendor prefix."""
    assert parse_model_spec("openai:openai/gpt-4o").model == "gpt-4o"


def test_default_model_when_nothing_is_given(monkeypatch) -> None:
    """With no argument and no EV_LLM_MODEL the default spec is used."""
    monkeypatch.delenv("EV_LLM_MODEL", raising=False)
    assert parse_model_spec(None).key == "openrouter:openai/gpt-4o"


def test_env_var_overrides_the_default_model(monkeypatch) -> None:
    """EV_LLM_MODEL selects the model without touching any call site."""
    monkeypatch.setenv("EV_LLM_MODEL", "openrouter:anthropic/claude-sonnet-4")
    assert parse_model_spec(None).model == "anthropic/claude-sonnet-4"


def test_variant_suffix_is_part_of_the_model_id(monkeypatch) -> None:
    """A colon inside a vendor-prefixed id is an OpenRouter variant, not a provider."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    spec = parse_model_spec("anthropic/claude-sonnet-4:beta")
    assert spec == ModelSpec("openrouter", "anthropic/claude-sonnet-4:beta")


def test_unsupported_provider_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported provider"):
        parse_model_spec("gemini:gemini-2.5-flash-lite")


def test_openrouter_is_preferred_when_both_keys_exist(monkeypatch) -> None:
    """OpenRouter is the default path; direct OpenAI is the fallback."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
    assert default_provider() == "openrouter"

    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert default_provider() == "openai"

    monkeypatch.delenv("OPENAI_API_KEY")
    assert default_provider() == "openrouter"


def test_keys_and_base_urls_per_provider(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    assert resolve_api_key("openrouter") == "or-key"
    assert resolve_api_key("openai") == "oai-key"
    assert resolve_base_url("openrouter") == "https://openrouter.ai/api/v1"
    assert resolve_base_url("openai") is None


def test_build_client_without_a_key_raises_a_named_error(monkeypatch) -> None:
    """No key means no client and no silent fallback to another provider."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        build_client(ModelSpec("openrouter", "openai/gpt-4o"))


# ---------------------------------------------------------------------------
# Usage accounting
# ---------------------------------------------------------------------------

def test_extract_token_counts_from_object_and_dict() -> None:
    obj = _FakeResponse(_FakeMessage("hi"), _FakeUsage(11, 5, 16))
    assert extract_token_counts(obj) == {
        "prompt_tokens": 11,
        "completion_tokens": 5,
        "total_tokens": 16,
    }
    as_dict = {"usage": {"prompt_tokens": 7, "completion_tokens": 3}}
    assert extract_token_counts(as_dict)["total_tokens"] == 10


def test_extract_token_counts_without_usage_is_all_none() -> None:
    counts = extract_token_counts(_FakeResponse(_FakeMessage("hi"), usage=None))
    assert counts == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }


def test_usage_accumulates_across_calls_and_flags_missing_usage() -> None:
    """Totals add up over a run; a response without usage is counted, not hidden."""
    usage = RunUsage()
    usage.add_response(_text_response("a", prompt=100, completion=10))
    usage.add_response(_text_response("b", prompt=250, completion=40))
    usage.add_response(_FakeResponse(_FakeMessage("c"), usage=None))
    usage.add_tool_call()

    assert usage.prompt_tokens == 350
    assert usage.completion_tokens == 50
    assert usage.total_tokens == 400
    assert usage.n_llm_calls == 3
    assert usage.n_tool_calls == 1
    assert usage.n_missing_usage == 1


def test_call_chat_records_every_call() -> None:
    """No model call can escape the accounting; latency is recorded per call."""
    client = _FakeClient([_text_response("ok", 12, 3)])
    recorder = RunRecorder(spec=ModelSpec("openrouter", "openai/gpt-4o"), arm="agent")
    call_chat(client, recorder, model="openai/gpt-4o", messages=[], temperature=0.0)

    assert recorder.usage.n_llm_calls == 1
    assert recorder.usage.total_tokens == 15
    assert recorder.rounds[0]["llm"]["latency_s"] >= 0.0


# ---------------------------------------------------------------------------
# Trace files
# ---------------------------------------------------------------------------

def test_recorder_writes_one_json_trace_per_run(tmp_path: Path) -> None:
    """The trace keeps the transcript, the tool call, and the final answer."""
    recorder = RunRecorder(
        spec=ModelSpec("openrouter", "openai/gpt-4o"),
        arm="agent",
        run_id="2019-06-15",
        request="Minimize energy cost for this day.",
    )
    recorder.record_llm_call(_tool_response('{"penalty_unmet": 1000000}'), 0.5, with_tools=True)
    recorder.record_tool_call(
        call_id="call_1",
        name="solve_ev_schedule",
        arguments={"penalty_unmet": 1e6},
        output={"success": True, "total_cost_usd": 1.25},
        latency_s=0.1,
    )
    recorder.record_llm_call(_text_response("Total cost is $1.25."), 0.4)
    recorder.finish(
        messages=[{"role": "user", "content": "hello"}],
        final_text="Total cost is $1.25.",
    )
    path = recorder.write(tmp_path)

    assert path == tmp_path / "agent" / "openrouter_openai_gpt-4o" / "2019-06-15.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["model"] == "openrouter:openai/gpt-4o"
    assert payload["answer"] == "Total cost is $1.25."
    assert payload["messages"] == [{"role": "user", "content": "hello"}]
    assert payload["usage"]["n_llm_calls"] == 2
    assert payload["usage"]["n_tool_calls"] == 1
    assert payload["usage"]["total_tokens"] == 2150
    tool = payload["trace"]["rounds"][0]["tools"][0]
    assert tool["name"] == "solve_ev_schedule"
    assert tool["arguments"] == {"penalty_unmet": 1e6}
    assert json.loads(tool["output"])["total_cost_usd"] == 1.25


# ---------------------------------------------------------------------------
# Baseline entry point
# ---------------------------------------------------------------------------

def test_baseline_reports_usage_and_persists_the_raw_response(
    tiny_problem, tmp_path: Path
) -> None:
    """The LLM-only arm returns tokens, calls, and seconds, and keeps its reply."""
    day, site, tou = tiny_problem
    reply = "Session 0: 6.6 6.6 0.0 0.0 0.0 0.0 0.0 0.0\nSession 1: 0.0 0.0 6.6 6.6 6.6 0.0 0.0 0.0"
    client = _FakeClient([_text_response(reply, prompt=1800, completion=120)])

    result = run_baseline(
        day=day, site=site, tou=tou,
        model="openrouter:openai/gpt-4o",
        client=client,
        run_id="2019-06-15",
        trace_dir=tmp_path,
    )

    assert result.raw_response == reply
    assert result.model == "openrouter:openai/gpt-4o"
    assert result.usage.prompt_tokens == 1800
    assert result.usage.completion_tokens == 120
    assert result.usage.total_tokens == 1920
    assert result.usage.n_llm_calls == 1
    assert result.usage.n_tool_calls == 0
    assert result.usage.wall_time_s >= 0.0

    payload = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    assert payload["arm"] == "baseline"
    assert payload["answer"] == reply
    assert [m["role"] for m in payload["messages"]] == ["system", "user", "assistant"]

    # The model id reaches the provider without the provider prefix, at T=0.
    assert client.calls[0]["model"] == "openai/gpt-4o"
    assert client.calls[0]["temperature"] == 0.0


def test_baseline_without_a_key_fails_without_calling_anything(
    tiny_problem, tmp_path: Path, monkeypatch
) -> None:
    """A missing key is reported against OpenRouter, not OpenAI."""
    day, site, tou = tiny_problem
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = run_baseline(
        day=day, site=site, tou=tou,
        model="openrouter:openai/gpt-4o",
        run_id="nokey",
        trace_dir=tmp_path,
    )

    assert result.parse_success is False
    assert "OPENROUTER_API_KEY" in (result.parse_error or "")
    assert result.usage.n_llm_calls == 0


def test_baseline_skips_the_call_when_there_is_nothing_to_schedule() -> None:
    """The empty day short-circuits before any client is built."""
    day = DaySessions(sessions=[], n_steps=8, dt_hours=0.25)
    site = SiteConfig(P_max_kw=20.0, n_steps=8, dt_hours=0.25)
    tou = TOUConfig(rates_per_kwh=np.full(8, 0.1))

    result = run_baseline(day=day, site=site, tou=tou, model="openrouter:openai/gpt-4o")

    assert result.parse_success is True
    assert result.usage.n_llm_calls == 0
    assert result.trace_path is None


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------

@requires_cvxpy
def test_agent_returns_usage_and_writes_a_trace(tiny_problem, tmp_path: Path) -> None:
    """One tool round then a text turn: two model calls, one tool call."""
    from agent.llm_agent import AgentLLMResult, run_agent_llm

    day, site, tou = tiny_problem
    client = _FakeClient([
        _tool_response('{"penalty_unmet": 1000000}', prompt=2400, completion=25),
        _text_response("The optimizer served both sessions.", prompt=2600, completion=90),
    ])

    result = run_agent_llm(
        day, site, tou,
        request="Minimize energy cost for this day.",
        model="openrouter:openai/gpt-4o",
        client=client,
        run_id="2019-06-15",
        trace_dir=tmp_path,
    )

    assert isinstance(result, AgentLLMResult)
    assert result.tool_called is True
    assert result.feasible is True
    assert result.explanation == "The optimizer served both sessions."
    assert result.usage.n_llm_calls == 2
    assert result.usage.n_tool_calls == 1
    assert result.usage.prompt_tokens == 5000
    assert result.usage.completion_tokens == 115
    assert result.usage.total_tokens == 5115
    assert result.usage.wall_time_s > 0.0

    payload = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    assert payload["arm"] == "agent"
    assert payload["trace"]["n_tool_calls"] == 1
    tool = payload["trace"]["rounds"][0]["tools"][0]
    assert tool["arguments"] == {"penalty_unmet": 1000000}
    assert json.loads(tool["output"])["success"] is True
    # The transcript keeps the solver's returned JSON as the model saw it.
    tool_messages = [m for m in payload["messages"] if m.get("role") == "tool"]
    assert json.loads(tool_messages[0]["content"])["pct_fully_served"] == 100.0


@requires_cvxpy
def test_agent_result_still_unpacks_as_the_legacy_six_tuple(
    tiny_problem, tmp_path: Path
) -> None:
    """agent.run.run_agent unpacks six values; that must keep working."""
    from agent.llm_agent import run_agent_llm

    day, site, tou = tiny_problem
    client = _FakeClient([
        _tool_response(),
        _text_response("Done."),
    ])

    (
        schedule,
        total_cost_usd,
        peak_load_kw,
        unmet_energy_kwh,
        feasible,
        explanation,
    ) = run_agent_llm(
        day, site, tou,
        model="openrouter:openai/gpt-4o",
        client=client,
        trace_dir=tmp_path,
    )

    assert schedule.shape == (2, 8)
    assert total_cost_usd > 0.0
    assert peak_load_kw > 0.0
    assert unmet_energy_kwh == pytest.approx(0.0, abs=1e-6)
    assert feasible is True
    assert explanation == "Done."


@requires_cvxpy
def test_agent_without_a_tool_call_reports_zero_tool_calls(
    tiny_problem, tmp_path: Path
) -> None:
    """A conceptual question is answered directly and the solver is not run."""
    from agent.llm_agent import run_agent_llm

    day, site, tou = tiny_problem
    client = _FakeClient([_text_response("TOU pricing charges more at peak hours.")])

    result = run_agent_llm(
        day, site, tou,
        request="What is TOU pricing?",
        model="openrouter:openai/gpt-4o",
        client=client,
        trace_dir=tmp_path,
    )

    assert result.tool_called is False
    assert result.feasible is False
    assert result.usage.n_llm_calls == 1
    assert result.usage.n_tool_calls == 0
    assert np.count_nonzero(result.schedule) == 0
    payload = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    assert payload["status"] == "no_tool_call"


@requires_cvxpy
def test_agent_never_writes_a_trace_when_asked_not_to(tiny_problem, tmp_path: Path) -> None:
    from agent.llm_agent import run_agent_llm

    day, site, tou = tiny_problem
    client = _FakeClient([_tool_response(), _text_response("Done.")])

    result = run_agent_llm(
        day, site, tou,
        model="openrouter:openai/gpt-4o",
        client=client,
        trace_dir=tmp_path,
        write_trace=False,
    )

    assert result.trace_path is None
    assert list(tmp_path.iterdir()) == []
