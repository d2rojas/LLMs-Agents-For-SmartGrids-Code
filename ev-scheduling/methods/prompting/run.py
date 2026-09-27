"""Single entry point: load env, get sessions, build prompt, call LLM, parse schedule."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import numpy as np

from config.llm import (
    ModelSpec,
    RunRecorder,
    RunUsage,
    build_client,
    call_chat,
    parse_model_spec,
)
from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions
from methods.prompting.prompt import build_prompt
from methods.prompting.parse import ParseResult, parse_llm_schedule


_SYSTEM_MESSAGE = (
    "You output ONLY the schedule: one line per session, each line "
    "'Session i: v0 v1 v2 ...' with exactly the number of space-separated "
    "floats specified in the prompt (one per time step). No commentary, "
    "no explanations. Follow the algorithm in the prompt. Ensure every "
    "line has the correct number of values; zeros outside each session's "
    "window, positive power inside until energy_kwh is delivered."
)


@dataclass
class BaselineResult:
    """Result of running the baseline.

    Attributes:
        schedule: Power schedule of shape (n_sessions, n_steps) in kW.
        parse_success: True if the model's text parsed into a schedule.
        raw_response: The model's reply, verbatim. Also persisted in the trace.
        parse_error: Why parsing or the call failed, if it did.
        usage: Prompt, completion, and total tokens, number of model calls,
            number of tool calls (always 0 for the LLM-only arm), and
            wall-clock seconds for this run.
        model: Resolved ``provider:model`` id that produced the run.
        trace_path: Path of the JSON trace written for this run, if any.
    """

    schedule: np.ndarray
    parse_success: bool
    raw_response: Optional[str] = None
    parse_error: Optional[str] = None
    usage: RunUsage = field(default_factory=RunUsage)
    model: str = ""
    trace_path: Optional[Path] = None


def _default_schedule(day: DaySessions) -> np.ndarray:
    """Return a zero schedule with the correct shape for the given day."""
    return np.zeros((len(day.sessions), day.n_steps), dtype=float)


def run_baseline(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    max_completion_tokens: int = 8192,
    instruction: Optional[str] = None,
    *,
    client: Optional[Any] = None,
    run_id: Optional[str] = None,
    trace_dir: Optional[Path] = None,
    write_trace: bool = True,
) -> BaselineResult:
    """Run baseline: build prompt, call the model, parse response to schedule.

    The call goes through ``config.llm``, so the provider is OpenRouter by
    default and direct OpenAI when an ``openai:<model>`` id is used. The call is
    timed and its usage accumulated, and the transcript plus the model's raw
    reply are written to a JSON trace next to the agent's traces.

    Token and cost safeguards:
      - If there are no sessions or no time steps, we skip the LLM call and
        immediately return a zero schedule.
      - The prompt is a single well-structured message (no long chat history).
      - `max_completion_tokens` bounds the output; callers can lower it.

    Args:
        day: DaySessions with sessions and horizon.
        site: SiteConfig with power cap.
        tou: TOUConfig with TOU rates.
        api_key: Provider key; falls back to OPENROUTER_API_KEY or
            OPENAI_API_KEY depending on the resolved provider.
        model: Model id as ``provider:model`` (e.g. ``openrouter:openai/gpt-4o``)
            or a bare id resolved against the default provider. Defaults to
            EV_LLM_MODEL, else ``openrouter:openai/gpt-4o``.
        max_completion_tokens: Cap on generated tokens.
        instruction: Optional extra instruction appended to the prompt.
        client: Pre-built client exposing ``chat.completions.create``. Used by
            tests; when given, no key is required and none is read.
        run_id: Identifier for the trace file, normally the day (e.g.
            "2019-06-15"). Defaults to a UTC timestamp.
        trace_dir: Root directory for traces; defaults to
            ``ev-scheduling/results/traces`` or ``EV_TRACE_DIR``.
        write_trace: Set False to skip writing the trace file.

    Returns:
        BaselineResult with the schedule, the raw reply, the accumulated usage,
        and the path of the trace.
    """
    # Basic consistency checks so we do not send inconsistent data to the model.
    if tou.n_steps != day.n_steps:
        raise ValueError(
            f"TOUConfig.n_steps ({tou.n_steps}) must match DaySessions.n_steps ({day.n_steps})."
        )
    if site.n_steps != day.n_steps:
        raise ValueError(
            f"SiteConfig.n_steps ({site.n_steps}) must match DaySessions.n_steps ({day.n_steps})."
        )
    if day.dt_hours <= 0.0:
        raise ValueError(f"DaySessions.dt_hours must be positive, got {day.dt_hours}.")

    spec: ModelSpec = parse_model_spec(model)

    # Trivial case: nothing to schedule.
    if len(day.sessions) == 0 or day.n_steps == 0:
        return BaselineResult(
            schedule=_default_schedule(day),
            parse_success=True,
            raw_response=None,
            parse_error=None,
            model=spec.key,
        )

    recorder = RunRecorder(
        spec=spec, arm="baseline", run_id=run_id or "", request=instruction
    )

    def _finish(
        *,
        schedule: np.ndarray,
        parse_success: bool,
        raw_response: Optional[str],
        parse_error: Optional[str],
        messages: Optional[List[dict]] = None,
        status: str = "ok",
    ) -> BaselineResult:
        """Close the recorder, write the trace, and build the result."""
        usage = recorder.finish(
            messages=messages,
            final_text=raw_response or "",
            status=status,
            error=parse_error,
        )
        path = recorder.write(trace_dir) if write_trace else None
        return BaselineResult(
            schedule=schedule,
            parse_success=parse_success,
            raw_response=raw_response,
            parse_error=parse_error,
            usage=usage,
            model=spec.key,
            trace_path=path,
        )

    # Build prompt text once; this is the only user message we send.
    prompt_text = build_prompt(day, site, tou, instruction=instruction)
    messages: List[dict] = [
        {"role": "system", "content": _SYSTEM_MESSAGE},
        {"role": "user", "content": prompt_text},
    ]

    # Build the client lazily so tests and key-free environments still import.
    if client is None:
        try:
            client = build_client(spec, api_key=api_key)
        except (ValueError, ImportError) as exc:
            return _finish(
                schedule=_default_schedule(day),
                parse_success=False,
                raw_response=None,
                parse_error=str(exc),
                messages=messages,
                status="no_client",
            )

    try:
        completion = call_chat(
            client,
            recorder,
            model=spec.model,
            messages=messages,
            max_tokens=max_completion_tokens,
            temperature=0.0,
        )
    except Exception as exc:  # pragma: no cover - depends on network and external API
        return _finish(
            schedule=_default_schedule(day),
            parse_success=False,
            raw_response=None,
            parse_error=f"Error while calling the {spec.provider} API: {exc}",
            messages=messages,
            status="api_error",
        )

    if not completion.choices:
        return _finish(
            schedule=_default_schedule(day),
            parse_success=False,
            raw_response=None,
            parse_error=f"The {spec.provider} API returned no choices.",
            messages=messages,
            status="empty_response",
        )

    response_text = completion.choices[0].message.content or ""
    messages.append({"role": "assistant", "content": response_text})

    # Parse the LLM output into a schedule matrix.
    parse_result: ParseResult = parse_llm_schedule(response_text, day)

    return _finish(
        schedule=parse_result.schedule,
        parse_success=parse_result.success,
        raw_response=response_text,
        parse_error=parse_result.error_message,
        messages=messages,
        status="ok" if parse_result.success else "parse_failed",
    )
