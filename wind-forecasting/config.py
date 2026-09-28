"""Site constants, budgets, and model resolution for the wind forecasting case study.

The task's numbers live here so no method can quietly run with a different one:
the sampling, the history window, the horizons, the physical power range, the
abnormal-data rules of the KDD Cup 2022 evaluation, and the budgets every method
with a loop is measured under.

Model ids are written ``provider:model`` as in the other case studies:

    openrouter:openai/gpt-4o-mini      (the default path; one key for the whole repo)
    openai:gpt-4o                      (direct OpenAI, needs OPENAI_API_KEY)
    none:rule_based                    (no model; the deterministic row)

Keys are read from the environment, then from ``.env`` files in increasing
priority: the power-flow project's ``.env`` (the shared OpenRouter key), then
this project's ``.env`` and ``.env.local``. Real environment variables always
win. The client is the OpenAI SDK pointed at the provider's base URL.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parent

# ---------------------------------------------------------------- the task

STEPS_PER_HOUR: int = 6            # 10-minute SCADA sampling
STEPS_PER_DAY: int = 144
HISTORY_DAYS: int = 14             # the window every method receives
HORIZONS_H = (3, 6, 48)            # the paper's three horizons
MAX_HORIZON_H: int = 48
TARGET_DAYS: int = 2               # 48 h = two dataset days
RATED_KW: float = 1500.0           # nominal turbine rating in the SDWPF farm
RANGE_MARGIN: float = 1.0667       # a reported value is in range up to rating * this
POWER_MAX_KW: float = RATED_KW * RANGE_MARGIN   # the nominal window's range; a scaled window carries its own

# The scaled condition, the memorisation check. One window is multiplied end to end, history and
# target together, by a factor drawn from this range with the instance's own seed, and its rating
# moves with it. The measurement stays real and its ground truth stays exact, because it is the
# same measurement transformed; what stops matching is any memorised copy of the published series.
# The same defence the power-flow case study uses when it perturbs the IEEE cases.
SCALE_RANGE = (0.82, 1.18)
FEATURES = ("Wspd", "Wdir", "Etmp", "Patv")   # the four columns the paper names

# KDD Cup 2022 abnormal-data rules (Zhou et al., SDWPF): a target point is not scored when
#   Patv is missing, or Patv <= 0 with Wspd > 2.5 m/s, or any pitch angle > 89 deg, or the
#   nacelle or wind direction is out of its physical range. Negative Patv is scored as 0.
ABNORMAL_WSPD: float = 2.5
ABNORMAL_PAB_DEG: float = 89.0
NDIR_RANGE_DEG: float = 720.0
WDIR_RANGE_DEG: float = 180.0

# KDD Cup split: the GRU trains on days 1..214; every evaluation target lies in 215..245.
TRAIN_LAST_DAY: int = 214
DATASET_DAYS: int = 245

# ---------------------------------------------------------------- budgets
#
# The same budget for every method that has a loop. The verification gate's
# retry is counted inside it, so the gated row cannot outrun the ungated one.

MAX_LLM_CALLS: int = int(os.environ.get("WIND_MAX_LLM_CALLS", "8"))
MAX_TOOL_CALLS: int = int(os.environ.get("WIND_MAX_TOOL_CALLS", "12"))
MAX_DUPLICATE_CALLS: int = 4        # repeated identical calls before the loop is sent to its final answer
REQUEST_TIMEOUT_S: float = float(os.environ.get("WIND_REQUEST_TIMEOUT_S", "600"))   # per request, wall clock
API_TIMEOUT_S: float = float(os.environ.get("WIND_API_TIMEOUT_S", "240"))           # one model call
MAX_RETRIES: int = int(os.environ.get("WIND_MAX_RETRIES", "2"))
DEFAULT_TEMPERATURE: float = 0.0
MAX_COMPLETION_TOKENS: int = 6000   # a 48 h forecast is 288 numbers, about 1,500 tokens, plus reasoning

# Tolerances of the gate and the scorer
TRACE_TOL_KW: float = 0.5           # a reported value matches a tool value within this
ANSWER_REL_TOL: float = 0.02        # the answer to the question, relative to what the forecast implies

# ---------------------------------------------------------------- env files

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL_SPEC = "openrouter:openai/gpt-4o-mini"

_ENV_FILES = (
    REPO_ROOT / "power-flow-agent" / ".env",
    REPO_ROOT / "power-flow-agent" / ".env.local",
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / ".env.local",
)


def _parse_env_file(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if k.strip():
            out[k.strip()] = v
    return out


def load_env_defaults() -> None:
    merged: Dict[str, str] = {}
    for p in _ENV_FILES:
        merged.update(_parse_env_file(p))
    for k, v in merged.items():
        os.environ.setdefault(k, v)


load_env_defaults()


# ---------------------------------------------------------------- models


@dataclass(frozen=True)
class ModelSpec:
    provider: str  # openrouter | openai | none
    model: str

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}"

    @property
    def short(self) -> str:
        """``openrouter:openai/gpt-4o-mini`` -> ``gpt-4o-mini``; ``none:*`` -> ``no-llm``."""
        if self.provider == "none":
            return "no-llm"
        return self.model.split("/")[-1].split(":")[-1]

    @property
    def uses_llm(self) -> bool:
        return self.provider != "none"


def parse_model_spec(raw: Optional[str] = None) -> ModelSpec:
    text = (raw or os.environ.get("WIND_LLM_MODEL") or DEFAULT_MODEL_SPEC).strip()
    provider, sep, model = text.partition(":")
    if sep and "/" in provider:
        provider, sep, model = "", "", text
    if not sep:
        provider = "openrouter" if os.environ.get("OPENROUTER_API_KEY") else ("openai" if os.environ.get("OPENAI_API_KEY") else "openrouter")
        model = text
    provider = provider.strip().lower()
    model = model.strip()
    if provider not in ("openrouter", "openai", "none"):
        raise ValueError(f"unsupported provider {provider!r}; use openrouter:, openai: or none:")
    if provider == "openrouter" and "/" not in model:
        model = "openai/" + model
    if provider == "openai" and model.startswith("openai/"):
        model = model.split("/", 1)[1]
    return ModelSpec(provider, model)


def api_key_for(spec: ModelSpec) -> str:
    if spec.provider == "openrouter":
        return os.environ.get("OPENROUTER_API_KEY", "").strip()
    if spec.provider == "openai":
        return os.environ.get("OPENAI_API_KEY", "").strip()
    return ""


def build_client(spec: ModelSpec) -> Any:
    """An ``openai.OpenAI`` client for the provider, with the request timeout and retries bounded."""
    key = api_key_for(spec)
    if not key:
        raise ValueError(f"no API key for provider {spec.provider!r} (model {spec.key}); put OPENROUTER_API_KEY or OPENAI_API_KEY in .env")
    from openai import OpenAI  # type: ignore[import]

    base_url = OPENROUTER_BASE_URL if spec.provider == "openrouter" else None
    return OpenAI(api_key=key, base_url=base_url, timeout=API_TIMEOUT_S, max_retries=MAX_RETRIES)


# ---------------------------------------------------------------- pricing


def load_pricing(path: Optional[Path] = None) -> Dict[str, Dict[str, float]]:
    p = path or (PROJECT_ROOT / "pricing.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def price_usd(spec: ModelSpec, prompt_tokens: int, completion_tokens: int, pricing: Optional[Dict[str, Dict[str, float]]] = None) -> Optional[float]:
    """Cost in USD from the pricing table (USD per million tokens), or None when the model is not priced."""
    table = pricing if pricing is not None else load_pricing()
    row = table.get(spec.key)
    if row is None:
        return None
    return round(prompt_tokens * row["input"] / 1e6 + completion_tokens * row["output"] / 1e6, 6)
