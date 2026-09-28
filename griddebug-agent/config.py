"""Site constants, budgets, and model resolution for the GridDebug case study.

Limits and budgets are the numbers every method is measured against; they
live here so that no method can quietly run with a different one.

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

V_MIN_PU: float = 0.95
V_MAX_PU: float = 1.05
MAX_LOADING_PERCENT: float = 100.0

NETWORKS = ("case14", "case30", "case57")
# Every system the harness can run. NETWORKS is what a run covers by default: the
# three of the submitted paper. 118 and 300 are the largest standard cases and the
# ones the power-flow case study uses; all twenty instances build on them too.
ALL_NETWORKS = ("case14", "case30", "case57", "case118", "case300")
NETWORK_LABELS = {"case14": "IEEE 14-bus", "case30": "IEEE 30-bus", "case57": "IEEE 57-bus",
                  "case118": "IEEE 118-bus", "case300": "IEEE 300-bus"}
NETWORK_FOLDER = {"case14": "ieee14", "case30": "ieee30", "case57": "ieee57", "case118": "ieee118",
                  "case300": "ieee300"}

# ---------------------------------------------------------------- budgets
#
# The same budget for every method that has a loop. The verification gate's
# retry is counted inside it, so the gated row cannot outrun the ungated one.

MAX_LLM_CALLS: int = int(os.environ.get("GD_MAX_LLM_CALLS", "20"))
MAX_TOOL_CALLS: int = int(os.environ.get("GD_MAX_TOOL_CALLS", "40"))
SCENARIO_TIMEOUT_S: float = float(os.environ.get("GD_SCENARIO_TIMEOUT_S", "600"))
REQUEST_TIMEOUT_S: float = float(os.environ.get("GD_REQUEST_TIMEOUT_S", "180"))
MAX_RETRIES: int = int(os.environ.get("GD_MAX_RETRIES", "2"))
DEFAULT_TEMPERATURE: float = 0.0
MAX_COMPLETION_TOKENS: int = 2000

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
    text = (raw or os.environ.get("GD_LLM_MODEL") or DEFAULT_MODEL_SPEC).strip()
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
    return OpenAI(api_key=key, base_url=base_url, timeout=REQUEST_TIMEOUT_S, max_retries=MAX_RETRIES)


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
