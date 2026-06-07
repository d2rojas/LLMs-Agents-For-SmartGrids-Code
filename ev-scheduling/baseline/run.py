"""Single entry point: load env, get sessions, build prompt, call LLM, parse schedule."""

from dataclasses import dataclass
import os
from typing import Optional

import numpy as np

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions
from baseline.prompt import build_prompt
from baseline.parse import ParseResult, parse_llm_schedule


@dataclass
class BaselineResult:
    """Result of running the baseline."""

    schedule: np.ndarray
    parse_success: bool
    raw_response: Optional[str] = None
    parse_error: Optional[str] = None


def _default_schedule(day: DaySessions) -> np.ndarray:
    """Return a zero schedule with the correct shape for the given day."""
    return np.zeros((len(day.sessions), day.n_steps), dtype=float)


def run_baseline(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    api_key: Optional[str] = None,
    model: str = "gpt-4o",
    max_completion_tokens: int = 8192,
    instruction: Optional[str] = None,
) -> BaselineResult:
    """Run baseline: build prompt, call OpenAI, parse response to schedule.

    Token and cost safeguards:
      - If there are no sessions or no time steps, we skip the LLM call and
        immediately return a zero schedule.
      - The prompt is a single well-structured message (no long chat history).
      - `max_completion_tokens` defaults to 2048 so we avoid unbounded output;
        callers can lower this further if needed.
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

    # Trivial case: nothing to schedule.
    if len(day.sessions) == 0 or day.n_steps == 0:
        return BaselineResult(
            schedule=_default_schedule(day),
            parse_success=True,
            raw_response=None,
            parse_error=None,
        )

    # Resolve API key from argument or environment.
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        return BaselineResult(
            schedule=_default_schedule(day),
            parse_success=False,
            raw_response=None,
            parse_error="OPENAI_API_KEY is not set; cannot call the baseline LLM.",
        )

    # Build prompt text once; this is the only user message we send.
    prompt_text = build_prompt(day, site, tou, instruction=instruction)

    # Lazily import the OpenAI client so that tests without the package can still run.
    try:
        from openai import OpenAI  # type: ignore[import]
    except ImportError as exc:  # pragma: no cover - environment-specific
        return BaselineResult(
            schedule=_default_schedule(day),
            parse_success=False,
            raw_response=None,
            parse_error=(
                "The 'openai' package is not installed. "
                "Install it with 'pip install openai>=1.0.0' to run the baseline. "
                f"Underlying error: {exc}"
            ),
        )

    client = OpenAI(api_key=key)

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You output ONLY the schedule: one line per session, each line "
                        "'Session i: v0 v1 v2 ...' with exactly the number of space-separated "
                        "floats specified in the prompt (one per time step). No commentary, "
                        "no explanations. Follow the algorithm in the prompt. Ensure every "
                        "line has the correct number of values; zeros outside each session's "
                        "window, positive power inside until energy_kwh is delivered."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt_text,
                },
            ],
            max_tokens=max_completion_tokens,
            temperature=0.0,
        )
    except Exception as exc:  # pragma: no cover - depends on network and external API
        return BaselineResult(
            schedule=_default_schedule(day),
            parse_success=False,
            raw_response=None,
            parse_error=f"Error while calling the OpenAI API: {exc}",
        )

    if not completion.choices:
        return BaselineResult(
            schedule=_default_schedule(day),
            parse_success=False,
            raw_response=None,
            parse_error="OpenAI API returned no choices.",
        )

    response_text = completion.choices[0].message.content or ""

    # Parse the LLM output into a schedule matrix.
    parse_result: ParseResult = parse_llm_schedule(response_text, day)

    return BaselineResult(
        schedule=parse_result.schedule,
        parse_success=parse_result.success,
        raw_response=response_text,
        parse_error=parse_result.error_message,
    )
