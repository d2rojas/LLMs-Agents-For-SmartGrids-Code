"""Blueprint-mode LLM-only heuristic AC power flow estimator."""

from __future__ import annotations

import json
import logging
import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Optional

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    GEMINI_TIMEOUT_S,
    MATPOWER_CASE_DATE,
    MATPOWER_DATA_ROOT,
)
from models.llm_only_schema import (
    DebugRoutingStep,
    PowerFlowResultSchema,
    TotalsSchema,
)
from solver.matpower_meta import get_matpower_meta
from solver.matpower_text import get_case_m_path, read_case_m_text


logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)


GEMINI_PROVIDER_ALIASES = {"gemini", "google"}
PROVIDER_ERROR = "LLM-only benchmark mode currently supports Gemini (google-genai) only. Please switch provider."
_LAST_RAW_RESPONSE: str = ""


def _set_last_raw_response(text: str) -> None:
    global _LAST_RAW_RESPONSE
    _LAST_RAW_RESPONSE = str(text or "")


def get_last_raw_response() -> str:
    return str(_LAST_RAW_RESPONSE or "")


def _is_physical_assertion_error(err: str) -> bool:
    s = str(err or "")
    # Physical checks only:
    # A1 slack angle, A2 load consistency, A3 power balance, A4 RATE_A semantics.
    return s.startswith("A1 failed:") or s.startswith("A2 failed:") or s.startswith("A3 failed:") or s.startswith("A4 failed:")


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        if not math.isfinite(x):
            return float(default)
        return x
    except Exception:
        return float(default)


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if isinstance(v, bool):
            return int(default)
        return int(v)
    except Exception:
        return int(default)


def _build_matpower_prompt(*, matpower_text: str, case_name: str, debug_mode: bool) -> tuple[str, str]:
    debug_note = (
        "debug_mode=true: include debug_routing_step with at most top 30 loads and top 50 branches."
        if debug_mode
        else "debug_mode=false: debug_routing_step must be null."
    )
    system_instruction = (
        "You are a Heuristic AC Power Flow Estimator.\n"
        "Perform step-by-step heuristic estimation internally before constructing the JSON. "
        "Ensure no prose or explanation exists outside the JSON object.\n"
        "Output ONLY the final RESULT JSON; do not repeat or reformat the input.\n"
        "Use ONLY the provided MATPOWER .m text as input data.\n"
        "Do not call external tools or numeric solvers.\n"
        "Return strict schema-valid JSON only.\n"
        "Hard constraints:\n"
        "- Keep MATPOWER 1-based indexing semantics.\n"
        "- bus_id must match MATPOWER BUS_I.\n"
        "- line_id must match MATPOWER branch row number (1-based).\n"
        "- Slack bus angle must be exactly va_deg = 0.0.\n"
        "- Enforce active-power balance: total_generation_mw = total_load_mw + total_loss_mw.\n"
        "- Respect voltage limits and branch thermal semantics.\n"
        "- If RATE_A == 0 for a branch, loading_percent must be 0.0 to safely render the graph.\n"
        f"- {debug_note}\n"
        "- If uncertain, return converged=false and explain in summary_text.\n"
        "Return the result strictly in this JSON format:\n"
        "{\n"
        '  "case_name": "string",\n'
        '  "converged": boolean,\n'
        '  "totals": {"total_generation_mw": float, "total_load_mw": float, "total_loss_mw": float},\n'
        '  "bus_voltages": [{"bus_id": int, "vm_pu": float, "va_deg": float}],\n'
        '  "line_flows": [{"line_id": int, "from_bus": int, "to_bus": int, "p_from_mw": float, "q_from_mvar": float, "loading_percent": float}],\n'
        '  "summary_text": "string"\n'
        "}"
    )
    user_text = (
        "CRITICAL: Do not mirror or echo the MATPOWER text. Proceed directly to power flow estimation "
        "and output the resulting JSON.\n"
        f"Analyze this MATPOWER case (case={case_name}, debug_mode={str(debug_mode).lower()}).\n\n"
        f"{matpower_text}"
    )
    return system_instruction, user_text


def build_matpower_prompt_preview(*, matpower_text: str, case_name: str, debug_mode: bool) -> str:
    """Return full prompt text (SYSTEM + USER) for UI inspection/logging."""
    system_instruction, user_text = _build_matpower_prompt(
        matpower_text=matpower_text,
        case_name=case_name,
        debug_mode=bool(debug_mode),
    )
    return f"[SYSTEM]\n{system_instruction}\n\n[USER]\n{user_text}"


def build_matpower_prompt_messages(*, matpower_text: str, case_name: str, debug_mode: bool) -> tuple[str, str]:
    """Return the raw system and user prompt components for benchmark runners."""
    return _build_matpower_prompt(
        matpower_text=matpower_text,
        case_name=case_name,
        debug_mode=bool(debug_mode),
    )


def validate_llm_output(
    *,
    raw_text: str,
    m_file_path: str,
    case_name: str,
    debug_mode: bool,
    relax_a2: bool = False,
) -> PowerFlowResultSchema:
    """Validate a raw LLM output string using the same checks as blueprint mode.

    This performs schema validation plus physical assertions, without making any LLM calls.
    """
    meta = get_matpower_meta(m_file_path)
    zero_rateA_line_ids = set(meta.zero_rateA_line_ids)

    try:
        parsed = PowerFlowResultSchema.model_validate_json(raw_text)
    except Exception as e1:
        obj = _extract_first_json_object(raw_text)
        if isinstance(obj, dict):
            try:
                coerced = _coerce_legacy_payload(obj)
                parsed = PowerFlowResultSchema.model_validate(coerced)
            except Exception:
                raise ValueError(f"schema validation failed: {type(e1).__name__}: {e1}") from e1
        else:
            raise ValueError(f"schema validation failed: {type(e1).__name__}: {e1}") from e1

    _autocorrect_zero_ratea_loading(
        parsed,
        zero_rateA_line_ids=zero_rateA_line_ids,
    )
    _assertions_or_raise(
        parsed,
        meta_total_load_mw_ref=meta.total_load_mw_ref,
        zero_rateA_line_ids=zero_rateA_line_ids,
        slack_bus_id_ref=meta.slack_bus_id_ref,
        debug_mode=bool(debug_mode),
        relax_a2=bool(relax_a2),
    )
    return parsed


def _build_retry_user_text(
    *,
    base_user_text: str,
    prev_output_json: str,
    retry_reason: str,
    total_load_mw_ref: float,
) -> str:
    return (
        "RETRY: Your previous output failed validation.\n"
        f"Failure reason: {retry_reason}\n"
        f"Hard requirement: totals.total_load_mw must equal {total_load_mw_ref:.2f} (abs_tol=0.05).\n"
        "Hard requirement: totals.total_generation_mw must equal totals.total_load_mw + totals.total_loss_mw "
        "(rel_tol=1e-3, abs_tol=0.5).\n"
        "Return ONLY corrected final RESULT JSON.\n\n"
        f"PREVIOUS_OUTPUT_JSON:\n{prev_output_json}\n\n"
        f"{base_user_text}"
    )


def _response_text(resp: Any) -> str:
    txt = getattr(resp, "text", None)
    if isinstance(txt, str) and txt.strip():
        return txt
    if txt is not None:
        return str(txt)

    # Fallback for SDK variants without `.text`.
    cands = getattr(resp, "candidates", None)
    if cands:
        chunks: list[str] = []
        for cand in cands:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) if content is not None else None
            if not parts:
                continue
            for p in parts:
                t = getattr(p, "text", None)
                if t is not None:
                    chunks.append(str(t))
        if chunks:
            return "\n".join(chunks)

    if hasattr(resp, "to_dict"):
        try:
            return json.dumps(resp.to_dict(), ensure_ascii=False)
        except Exception:
            pass
    return str(resp)


def _extract_first_json_object(text: str) -> Optional[dict[str, Any]]:
    s = str(text or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(s[start : end + 1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None
    return None


def _coerce_legacy_payload(obj: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    out["case_name"] = str(obj.get("case_name", obj.get("case", "unknown_case")))
    out["converged"] = bool(obj.get("converged", obj.get("success", True)))

    totals_in = obj.get("totals")
    if isinstance(totals_in, dict):
        out["totals"] = {
            "total_generation_mw": _safe_float(totals_in.get("total_generation_mw")),
            "total_load_mw": _safe_float(totals_in.get("total_load_mw")),
            "total_loss_mw": _safe_float(totals_in.get("total_loss_mw")),
        }
    else:
        out["totals"] = {
            "total_generation_mw": _safe_float(obj.get("total_generation_mw", obj.get("total_generation"))),
            "total_load_mw": _safe_float(obj.get("total_load_mw", obj.get("total_load"))),
            "total_loss_mw": _safe_float(obj.get("total_loss_mw", obj.get("total_loss"))),
        }

    if isinstance(obj.get("bus_voltages"), list):
        out["bus_voltages"] = obj.get("bus_voltages")
    elif isinstance(obj.get("bus_results"), list):
        buses: list[dict[str, Any]] = []
        for i, b in enumerate(obj.get("bus_results") or []):
            if not isinstance(b, dict):
                continue
            bus_id = b.get("bus_id", b.get("id", i + 1))
            buses.append(
                {
                    "bus_id": _safe_int(bus_id, i + 1),
                    "vm_pu": _safe_float(b.get("vm_pu", b.get("vm", 1.0)), 1.0),
                    "va_deg": _safe_float(b.get("va_deg", b.get("va", 0.0)), 0.0),
                }
            )
        out["bus_voltages"] = buses
    else:
        out["bus_voltages"] = []

    if isinstance(obj.get("line_flows"), list):
        out["line_flows"] = obj.get("line_flows")
    elif isinstance(obj.get("branch_results"), list):
        lines: list[dict[str, Any]] = []
        for i, l in enumerate(obj.get("branch_results") or []):
            if not isinstance(l, dict):
                continue
            lines.append(
                {
                    "line_id": _safe_int(l.get("line_id", l.get("id", i + 1)), i + 1),
                    "from_bus": _safe_int(l.get("from_bus", l.get("f_bus", 0)), 0),
                    "to_bus": _safe_int(l.get("to_bus", l.get("t_bus", 0)), 0),
                    "p_from_mw": _safe_float(l.get("p_from_mw", l.get("p_mw", 0.0))),
                    "q_from_mvar": _safe_float(l.get("q_from_mvar", l.get("q_mvar", 0.0))),
                    "loading_percent": (
                        0.0
                        if l.get("loading_percent", l.get("loading", l.get("loading_percent_value"))) is None
                        else _safe_float(l.get("loading_percent", l.get("loading", l.get("loading_percent_value"))))
                    ),
                }
            )
        out["line_flows"] = lines
    else:
        out["line_flows"] = []

    out["voltage_violations"] = obj.get("voltage_violations") if isinstance(obj.get("voltage_violations"), list) else []
    out["thermal_violations"] = obj.get("thermal_violations") if isinstance(obj.get("thermal_violations"), list) else []
    out["summary_text"] = str(obj.get("summary_text", obj.get("summary", "")))
    out["debug_routing_step"] = obj.get("debug_routing_step", None)

    return out


def _is_input_echo_payload(obj: dict[str, Any]) -> bool:
    keys = set(obj.keys())
    return {"baseMVA", "bus", "gen", "branch"}.issubset(keys)


def _build_failure_result(case_name: str, reason: str) -> PowerFlowResultSchema:
    return PowerFlowResultSchema(
        case_name=str(case_name or "unknown_case"),
        converged=False,
        totals=TotalsSchema(
            total_generation_mw=0.0,
            total_load_mw=0.0,
            total_loss_mw=0.0,
        ),
        bus_voltages=[],
        line_flows=[],
        voltage_violations=[],
        thermal_violations=[],
        summary_text=f"LLM-only blueprint failed: {reason}",
        debug_routing_step=None,
    )


def _autocorrect_zero_ratea_loading(
    result: PowerFlowResultSchema,
    *,
    zero_rateA_line_ids: set[int],
) -> int:
    corrected = 0
    for lf in result.line_flows:
        lid = int(lf.line_id)
        if lid in zero_rateA_line_ids and (lf.loading_percent is None or not math.isclose(float(lf.loading_percent), 0.0, rel_tol=0.0, abs_tol=1e-9)):
            lf.loading_percent = 0.0
            corrected += 1

    if corrected > 0 and result.thermal_violations:
        result.thermal_violations = [
            tv for tv in result.thermal_violations if int(tv.line_id) not in zero_rateA_line_ids
        ]

    if corrected > 0:
        note = f" Auto-corrected {corrected} RATE_A==0 line(s): loading_percent set to 0.0."
        result.summary_text = (str(result.summary_text or "") + note).strip()

    return corrected


def _assertions_or_raise(
    result: PowerFlowResultSchema,
    *,
    meta_total_load_mw_ref: float,
    zero_rateA_line_ids: set[int],
    slack_bus_id_ref: int,
    debug_mode: bool,
    relax_a2: bool = False,
) -> None:
    bus_by_id = {int(b.bus_id): b for b in result.bus_voltages}
    slack = bus_by_id.get(int(slack_bus_id_ref))
    if slack is None:
        raise AssertionError(f"A1 failed: slack bus {slack_bus_id_ref} not found in bus_voltages.")
    if not math.isclose(float(slack.va_deg), 0.0, rel_tol=0.0, abs_tol=1e-9):
        raise AssertionError(f"A1 failed: slack bus {slack_bus_id_ref} va_deg must be 0.0.")

    if not relax_a2:
        if not math.isclose(
            float(result.totals.total_load_mw),
            float(meta_total_load_mw_ref),
            rel_tol=0.0,
            abs_tol=0.05,
        ):
            raise AssertionError(
                f"A2 failed: totals.total_load_mw={result.totals.total_load_mw} "
                f"!= ref={meta_total_load_mw_ref} within abs_tol=0.05."
            )

    if not math.isclose(
        float(result.totals.total_generation_mw),
        float(result.totals.total_load_mw + result.totals.total_loss_mw),
        rel_tol=1e-3,
        abs_tol=0.5,
    ):
        raise AssertionError(
            "A3 failed: total_generation_mw must equal total_load_mw + total_loss_mw "
            "(rel_tol=1e-3, abs_tol=0.5)."
        )

    for lf in result.line_flows:
        lid = int(lf.line_id)
        if lid in zero_rateA_line_ids and not math.isclose(float(lf.loading_percent or 0.0), 0.0, rel_tol=0.0, abs_tol=1e-9):
            raise AssertionError(
                f"A4 failed: line_id={lid} has RATE_A==0 so loading_percent must be 0.0."
            )

    if not debug_mode:
        if result.debug_routing_step is not None:
            raise AssertionError("A5 failed: debug_mode=false requires debug_routing_step=null.")
        return

    debug: Optional[DebugRoutingStep] = result.debug_routing_step
    if debug is None:
        raise AssertionError("A5 failed: debug_mode=true requires debug_routing_step.")

    if len(debug.path_assignments) > 30:
        raise AssertionError("A5 failed: debug.path_assignments exceeds Top 30.")
    if len(debug.branch_pd_sums) > 50:
        raise AssertionError("A5 failed: debug.branch_pd_sums exceeds Top 50.")

    flow_by_line_id = {int(lf.line_id): lf for lf in result.line_flows}
    for b in debug.branch_pd_sums:
        lid = int(b.line_id)
        lf = flow_by_line_id.get(lid)
        if lf is None:
            raise AssertionError(f"A5 failed: debug line_id={lid} missing in line_flows.")
        if not math.isclose(float(lf.p_from_mw), float(b.pd_sum_mw), rel_tol=0.0, abs_tol=1e-6):
            raise AssertionError(
                f"A5 failed: debug branch line_id={lid} pd_sum_mw={b.pd_sum_mw} "
                f"!= line_flows.p_from_mw={lf.p_from_mw}."
            )


def _generate_json_with_gemini(
    *,
    system_instruction: str,
    user_text: str,
    llm_model: str,
    api_key: str,
    temperature: float,
) -> str:
    try:
        from google import genai
        from google.genai import types
    except Exception as e:  # pragma: no cover - depends on runtime env
        raise RuntimeError(
            "google-genai is required for LLM-only blueprint mode. Install it via `pip install google-genai`."
        ) from e

    cfg_kwargs = {
        "system_instruction": system_instruction,
        "temperature": float(temperature),
        "response_mime_type": "application/json",
        "max_output_tokens": 16384,
    }

    cfg = types.GenerateContentConfig(**cfg_kwargs)

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=llm_model,
        contents=user_text,
        config=cfg,
    )
    return _response_text(resp)


def _repair_json_with_gemini(
    *,
    llm_model: str,
    api_key: str,
    temperature: float,
    broken_output: str,
) -> str:
    try:
        from google import genai
        from google.genai import types
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "google-genai is required for LLM-only blueprint mode. Install it via `pip install google-genai`."
        ) from e

    repair_instruction = (
        "Fix the following invalid JSON into the target RESULT JSON schema.\n"
        "Do not output reasoning.\n"
        "Output only one JSON object."
    )
    repair_user = (
        "Rewrite this into a valid RESULT JSON with keys: "
        "case_name, converged, totals{total_generation_mw,total_load_mw,total_loss_mw}, "
        "bus_voltages[], line_flows[], voltage_violations[], thermal_violations[], summary_text, debug_routing_step.\n\n"
        f"INVALID_OUTPUT:\n{broken_output}"
    )
    cfg = types.GenerateContentConfig(
        system_instruction=repair_instruction,
        temperature=float(temperature),
        response_mime_type="application/json",
        max_output_tokens=8192,
    )
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=llm_model,
        contents=repair_user,
        config=cfg,
    )
    return _response_text(resp)


def _call_with_timeout(fn: Any, timeout_s: float) -> Any:
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        return fut.result(timeout=max(float(timeout_s), 1e-3))


def solve_from_matpower_text(
    *,
    matpower_text: str,
    m_file_path: str,
    case_name: str,
    debug_mode: bool,
    llm_provider: str,
    llm_model: str,
    api_key: str,
    temperature: float,
    timeout_s: float,
) -> PowerFlowResultSchema:
    MAX_RETRIES_FOR_A2_A3 = 2
    last_raw_response: str = ""

    provider = str(llm_provider or "").strip().lower()
    if provider not in GEMINI_PROVIDER_ALIASES:
        raise ValueError(PROVIDER_ERROR)

    model = str(llm_model or "").strip() or GEMINI_MODEL
    key = str(api_key or "").strip() or str(GEMINI_API_KEY or "").strip()
    temp = float(temperature if temperature is not None else GEMINI_TEMPERATURE)
    timeout = float(timeout_s if timeout_s is not None else GEMINI_TIMEOUT_S)

    if not key:
        _set_last_raw_response(last_raw_response)
        return _build_failure_result(case_name, "Gemini API key is missing.")

    try:
        meta = get_matpower_meta(m_file_path)
    except Exception as e:
        _set_last_raw_response(last_raw_response)
        return _build_failure_result(case_name, f"metadata extraction failed: {type(e).__name__}: {e}")
    zero_rateA_line_ids = set(meta.zero_rateA_line_ids)

    system_instruction, user_text = _build_matpower_prompt(
        matpower_text=matpower_text,
        case_name=case_name,
        debug_mode=bool(debug_mode),
    )

    current_user_text = user_text
    last_assert_err: Optional[str] = None
    for attempt in range(0, MAX_RETRIES_FOR_A2_A3 + 1):
        try:
            raw_text = _call_with_timeout(
                lambda: _generate_json_with_gemini(
                    system_instruction=system_instruction,
                    user_text=current_user_text,
                    llm_model=model,
                    api_key=key,
                    temperature=temp,
                ),
                timeout_s=timeout,
            )
            last_raw_response = str(raw_text or "")
        except FutureTimeoutError:
            _set_last_raw_response(last_raw_response)
            return _build_failure_result(case_name, f"timeout after {timeout:.1f}s")
        except Exception as e:
            _set_last_raw_response(last_raw_response)
            return _build_failure_result(case_name, f"gemini request failed: {type(e).__name__}: {e}")

        try:
            parsed = PowerFlowResultSchema.model_validate_json(raw_text)
        except Exception as e1:
            obj = _extract_first_json_object(raw_text)
            if isinstance(obj, dict):
                try:
                    coerced = _coerce_legacy_payload(obj)
                    parsed = PowerFlowResultSchema.model_validate(coerced)
                except Exception:
                    try:
                        repaired_raw = _call_with_timeout(
                            lambda: _repair_json_with_gemini(
                                llm_model=model,
                                api_key=key,
                                temperature=temp,
                                broken_output=raw_text if not _is_input_echo_payload(obj) else json.dumps(obj, ensure_ascii=False),
                            ),
                            timeout_s=timeout,
                        )
                        last_raw_response = str(repaired_raw or last_raw_response)
                        parsed = PowerFlowResultSchema.model_validate_json(repaired_raw)
                    except Exception as e2:
                        _set_last_raw_response(last_raw_response)
                        return _build_failure_result(
                            case_name,
                            f"schema validation failed: {type(e1).__name__}: {e1}; repair failed: {type(e2).__name__}: {e2}",
                        )
            else:
                _set_last_raw_response(last_raw_response)
                return _build_failure_result(case_name, f"schema validation failed: {type(e1).__name__}: {e1}")

        try:
            _autocorrect_zero_ratea_loading(
                parsed,
                zero_rateA_line_ids=zero_rateA_line_ids,
            )
            _assertions_or_raise(
                parsed,
                meta_total_load_mw_ref=meta.total_load_mw_ref,
                zero_rateA_line_ids=zero_rateA_line_ids,
                slack_bus_id_ref=meta.slack_bus_id_ref,
                debug_mode=bool(debug_mode),
                relax_a2=False,
            )
            _set_last_raw_response(last_raw_response)
            return parsed
        except Exception as e:
            err = str(e)
            last_assert_err = err
            should_retry = _is_physical_assertion_error(err) and attempt < MAX_RETRIES_FOR_A2_A3
            if not should_retry:
                _set_last_raw_response(last_raw_response)
                return _build_failure_result(case_name, err)
            current_user_text = _build_retry_user_text(
                base_user_text=user_text,
                prev_output_json=raw_text,
                retry_reason=err,
                total_load_mw_ref=float(meta.total_load_mw_ref),
            )

    _set_last_raw_response(last_raw_response)
    return _build_failure_result(case_name, f"validation failed after retries: {last_assert_err or 'unknown'}")


def solve_with_llm(
    net: Any,
    *,
    api_key: str,
    model: str,
    base_url: Optional[str] = None,  # kept for backward compatibility
    temperature: float = 0.0,
    timeout_s: float = 90.0,
    v_min: float = 0.95,  # unused by blueprint output generation
    v_max: float = 1.05,  # unused by blueprint output generation
    max_loading: float = 100.0,  # unused by blueprint output generation
    llm_provider: str = "gemini",
    debug_mode: bool = False,
    matpower_data_root: str = MATPOWER_DATA_ROOT,
    matpower_case_date: str = MATPOWER_CASE_DATE,
) -> PowerFlowResultSchema:
    """Compatibility wrapper that reads MATPOWER text then runs blueprint solve."""

    _ = (base_url, v_min, v_max, max_loading)  # intentionally unused
    case_name = str(getattr(net, "_case_name", None) or getattr(net, "name", None) or "case14")
    m_path = get_case_m_path(case_name, date=matpower_case_date, root=matpower_data_root)
    matpower_text = read_case_m_text(case_name, date=matpower_case_date, root=matpower_data_root)

    return solve_from_matpower_text(
        matpower_text=matpower_text,
        m_file_path=str(m_path),
        case_name=case_name,
        debug_mode=bool(debug_mode),
        llm_provider=llm_provider,
        llm_model=model,
        api_key=api_key,
        temperature=temperature,
        timeout_s=timeout_s,
    )
