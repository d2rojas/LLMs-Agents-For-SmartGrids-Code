"""config.py

全局配置：
- LLM API key / 模型选择
- 默认阈值参数（电压越限、热稳定越限）

说明：
- Streamlit Cloud 部署时通过 st.secrets 注入密钥。
- 本地开发时使用 .env.local 文件。
- 优先级：环境变量 > st.secrets > .env.local
"""

from __future__ import annotations

import os
from pathlib import Path


def _strip_wrapping_quotes(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        return v[1:-1]
    return v


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        out[key] = _strip_wrapping_quotes(value)
    return out


def _load_local_env_defaults() -> None:
    """Load .env/.env.local defaults without overriding process environment."""
    root = Path(__file__).resolve().parent
    merged: dict[str, str] = {}
    merged.update(_parse_env_file(root / ".env"))
    merged.update(_parse_env_file(root / ".env.local"))
    for k, v in merged.items():
        if k not in os.environ:
            os.environ[k] = v


_load_local_env_defaults()


def _get_secret(name: str, default: str | None = None) -> str | None:
    """Read a config value: env var > st.secrets > default."""
    val = os.getenv(name)
    if val:
        return val
    try:
        import streamlit as st  # noqa: F811
        val = st.secrets.get(name)
        if val:
            return str(val)
    except Exception:
        pass
    return default


# -----------------------------
# LLM
# -----------------------------

OPENAI_API_KEY: str | None = _get_secret("OPENAI_API_KEY")
OPENAI_MODEL: str = _get_secret("OPENAI_MODEL", "gpt-4o-mini")  # type: ignore[assignment]
OPENAI_TEMPERATURE: float = float(_get_secret("OPENAI_TEMPERATURE", "0.0"))  # type: ignore[arg-type]
OPENAI_TIMEOUT_S: float = float(_get_secret("OPENAI_TIMEOUT_S", "60"))  # type: ignore[arg-type]

GEMINI_API_KEY: str | None = (
    _get_secret("GEMINI_API_KEY")
    or _get_secret("GOOGLE_API_KEY")
)
GEMINI_MODEL: str = _get_secret("GEMINI_MODEL", "gemini-2.5-flash-lite")  # type: ignore[assignment]
GEMINI_TEMPERATURE: float = float(_get_secret("GEMINI_TEMPERATURE", _get_secret("LLM_TEMPERATURE", "0.0")))  # type: ignore[arg-type]
GEMINI_TIMEOUT_S: float = float(_get_secret("GEMINI_TIMEOUT_S", _get_secret("LLM_TIMEOUT_S", "60")))  # type: ignore[arg-type]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(_get_secret(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "t", "yes", "y", "on"}


# MATPOWER text dataset (for blueprint-mode llm_only)
MATPOWER_DATA_ROOT: str = _get_secret("MATPOWER_DATA_ROOT", "data/matpower")  # type: ignore[assignment]
MATPOWER_CASE_DATE: str = _get_secret("MATPOWER_CASE_DATE", "2017-01-01")  # type: ignore[assignment]
LLM_ONLY_DEBUG_MODE: bool = _env_bool("LLM_ONLY_DEBUG_MODE", default=False)


# -----------------------------
# Validation thresholds
# -----------------------------

DEFAULT_V_MIN: float = float(_get_secret("V_MIN", "0.95"))  # type: ignore[arg-type]
DEFAULT_V_MAX: float = float(_get_secret("V_MAX", "1.05"))  # type: ignore[arg-type]
DEFAULT_MAX_LOADING: float = float(_get_secret("MAX_LOADING", "100"))  # type: ignore[arg-type]
