"""Traceability: does every number in the answer come from the last solve?

This replaces what this project used to call *faithfulness*. The power-flow case
study reports the same quantity per answer under ``faithful_answers``
(``benchmarks/metrics.py::faithful_numbers`` plus ``stale_state_check``); the
names here are aligned with it, and the vocabulary of the paper is *traceable*.

Two checks, one verdict per answer:

* **traceable numbers**: every number the answer states matches a number in a
  tool output (within tolerance), or merely echoes the request.
* **from the last solve**: no number matches only an output of an earlier solve.
  An answer quoting both an old and a new value is a before/after comparison and
  is not penalised, the same rule as ``stale_state_quoted_old``.

``TraceabilityResult.traceable`` is the conjunction, and the reported column is
the share of ANSWERS in which every number traces, not the mean of each answer's
own traceable-number share. A per-number mean lets a handful of badly
contaminated answers barely move the aggregate.

Tolerances: $0.01 for cost, 0.01 kW for power, 0.01 kWh for energy, and 0.01 for
a bare percentage, all absolute.

Two limits, real and stated in the paper
----------------------------------------
1. ``derived_numbers_count_as_untraceable``: a number correctly derived from two
   tool outputs, a difference of totals for instance, appears in neither output
   and is counted untraceable. The check measures quotation, not arithmetic, so
   it under-counts correct answers.
2. ``chance_match_within_tolerance``: a fabricated number can fall within
   tolerance of an unrelated value that happens to be in a tool output, and is
   then counted traceable. The check over-counts in the other direction.

Both are attached to every result in ``TraceabilityResult.limitations`` so a
harness that persists rows keeps them next to the number they qualify.

Relation to ``evaluation/faithfulness/faithfulness.py``: that module compares
four named quantities parsed out of the v1 template (``"Total cost: $X."``) and
is called by no harness. Its tolerance idea is sound and its four quantities are
the ones that matter, so they are kept; its template regexes are not, because the
agent's answers are free-form. This module scans free-form text for every number
and matches against the tool outputs themselves, so nothing has to be named in a
fixed sentence to be checked.
"""

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Absolute tolerances, in the unit of the quantity.
TOL_COST_USD = 0.01
TOL_PEAK_KW = 0.01
TOL_UNMET_KWH = 0.01
TOL_DEFAULT = 0.01

TOLERANCE_BY_KIND: Dict[str, float] = {
    "cost": TOL_COST_USD,
    "power": TOL_PEAK_KW,
    "energy": TOL_UNMET_KWH,
    "percent": TOL_DEFAULT,
    "unknown": TOL_DEFAULT,
}

LIMITATIONS: Tuple[str, ...] = (
    "derived_numbers_count_as_untraceable",
    "chance_match_within_tolerance",
)

# Numbers with these units are times, not results: they restate the request's
# arrival and departure, never appear in a solver output, and would otherwise be
# counted as untraceable.
_IGNORED_KINDS: frozenset = frozenset({"time"})

_NUM_RE = re.compile(
    r"(?P<dollar>\$\s*)?"
    r"(?<![\w.])"
    r"(?P<num>[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?)"
    r"(?P<unit>\s*(?:usd\b|dollars?\b|kwh\b|mwh\b|kw\b|mw\b|%|percent\b|"
    r"hours?\b|hrs?\b|h\b|minutes?\b|mins?\b|am\b|pm\b))?",
    flags=re.IGNORECASE,
)
# "EV 3", "session 12", "charger 4", "step 40": an identifier, not a quantity.
_ID_PREFIX_RE = re.compile(
    r"(?:\b(?:ev|evs|car|cars|vehicle|vehicles|session|sessions|charger|chargers|station|stations|"
    r"step|steps|slot|interval|id|no\.?|number|#)\s*[-#:]?\s*$)",
    flags=re.IGNORECASE,
)
# "9:30", "17:00": clock times are removed before scanning.
_CLOCK_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\b", flags=re.IGNORECASE)


@dataclass(frozen=True)
class NumberMention:
    """One number stated in an answer.

    Attributes:
        value: Parsed numeric value.
        kind: "cost" | "power" | "energy" | "percent" | "time" | "unknown".
        text: The matched text, for reporting.
        decimals: Digits written after the decimal point, i.e. the precision the
            answer quoted the value with.
    """

    value: float
    kind: str
    text: str
    decimals: int


@dataclass
class TraceabilityResult:
    """Per-answer verdict.

    Attributes:
        traceable: Every number traces to a tool output and none of them comes
            only from an earlier solve. This is the value the column averages.
        numbers_traceable: Every number matches some tool output (last solve or
            earlier) or echoes the request.
        from_last_solve: No number matches only a pre-last-solve output.
        n_numbers: Numbers considered (times and bare identifiers excluded).
        n_untraceable: How many matched no tool output.
        untraceable: Their texts, for inspection.
        quoted_prior_solve: Texts of numbers that match only an earlier solve.
        limitations: LIMITATIONS, carried on every result so that a stored row
            keeps the caveats next to the verdict.
        detail: Short human-readable summary.
    """

    traceable: bool
    numbers_traceable: bool
    from_last_solve: bool
    n_numbers: int
    n_untraceable: int
    untraceable: List[str] = field(default_factory=list)
    quoted_prior_solve: List[str] = field(default_factory=list)
    limitations: Tuple[str, ...] = LIMITATIONS
    detail: str = ""


def _unit_kind(dollar: Optional[str], unit: Optional[str]) -> str:
    """Map the matched currency sign or unit to a quantity kind."""
    if dollar:
        return "cost"
    u = (unit or "").strip().lower().replace(" ", "")
    if not u:
        return "unknown"
    if u in ("usd", "dollar", "dollars"):
        return "cost"
    if u in ("kwh", "mwh"):
        return "energy"
    if u in ("kw", "mw"):
        return "power"
    if u in ("%", "percent"):
        return "percent"
    return "time"


def numbers_in_text(text: Optional[str]) -> List[NumberMention]:
    """Numbers an answer states, as NumberMention entries.

    Skipped: clock times, numbers glued to an identifier word ("EV 3"), bare
    integers with no unit (counts, ids, list numbering), and numbers carrying a
    time unit, none of which is a solver result.
    """
    s = _CLOCK_RE.sub(" ", str(text or ""))
    out: List[NumberMention] = []
    for m in _NUM_RE.finditer(s):
        raw = m.group("num")
        kind = _unit_kind(m.group("dollar"), m.group("unit"))
        if kind in _IGNORED_KINDS:
            continue
        before = s[max(0, m.start("num") - 16) : m.start("num")]
        if kind == "unknown" and _ID_PREFIX_RE.search(before):
            continue
        if kind == "unknown" and "." not in raw:
            continue  # bare integer: id, count or numbering
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if not math.isfinite(value):
            continue
        decimals = len(raw.split(".", 1)[1]) if "." in raw else 0
        out.append(NumberMention(value=value, kind=kind, text=m.group(0).strip(), decimals=decimals))
    return out


def _walk_numbers(obj: Any, acc: List[float]) -> None:
    """Collect every finite number in a nested JSON-like structure."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        if math.isfinite(float(obj)):
            acc.append(float(obj))
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _walk_numbers(v, acc)
        return
    if isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_numbers(v, acc)


def numbers_in_tool_outputs(tool_outputs: Iterable[Any]) -> List[float]:
    """Every finite number in the tool outputs (dicts, or their JSON strings)."""
    acc: List[float] = []
    for out in tool_outputs or []:
        obj: Any = out
        if isinstance(out, str):
            try:
                obj = json.loads(out)
            except Exception:
                for m in re.finditer(r"[-+]?\d+(?:\.\d+)?", out):
                    try:
                        acc.append(float(m.group(0)))
                    except ValueError:
                        continue
                continue
        _walk_numbers(obj, acc)
    return acc


def _request_candidates(request_text: Optional[str]) -> List[float]:
    """Numbers that merely echo the request (site cap, prices, requested energy)."""
    if not request_text:
        return []
    cands = [n.value for n in numbers_in_text(request_text)]
    for m in re.finditer(r"[-+]?\d+(?:\.\d+)?", str(request_text)):
        try:
            cands.append(float(m.group(0)))
        except ValueError:
            continue
    return cands


def _matches(
    mention: NumberMention,
    candidates: Sequence[float],
    *,
    allow_rounded_quotes: bool = True,
) -> bool:
    """Does this number match any candidate within its kind's tolerance?

    With ``allow_rounded_quotes`` a value quoted with k decimals also matches a
    candidate whose rounding to k decimals equals it ("$24.1" for 24.13), so a
    coarser quotation of a solver value is not scored as fabricated. Same rule as
    the power-flow ``_matches``.
    """
    tol = TOLERANCE_BY_KIND.get(mention.kind, TOL_DEFAULT)
    for c in candidates:
        if abs(mention.value - c) <= tol:
            return True
        if allow_rounded_quotes and abs(round(c, mention.decimals) - mention.value) <= 1e-9:
            return True
    return False


def check_traceability(
    answer_text: Optional[str],
    tool_outputs: Iterable[Any],
    *,
    prior_tool_outputs: Iterable[Any] = (),
    request_text: Optional[str] = None,
    allow_rounded_quotes: bool = True,
) -> TraceabilityResult:
    """Check one answer against the tool outputs it should be quoting.

    Args:
        answer_text: The free-form answer the system returned.
        tool_outputs: Outputs of the **last** solve, as the dicts the tool
            returned or their JSON strings.
        prior_tool_outputs: Outputs of earlier solves in the same episode. Needed
            to tell "quoted an old value" from "invented a value"; pass an empty
            sequence when the episode had a single solve.
        request_text: The request, so numbers that merely echo it (the site cap,
            the tariff, a requested energy) are not scored as fabricated.
        allow_rounded_quotes: See ``_matches``.

    Returns:
        TraceabilityResult. An answer with no numbers is ``traceable`` True with
        ``n_numbers`` 0: it states nothing unsupported. Callers that want to
        exclude such answers can filter on ``n_numbers``.
    """
    mentions = numbers_in_text(answer_text)
    last = numbers_in_tool_outputs(tool_outputs)
    prior = numbers_in_tool_outputs(prior_tool_outputs)
    echo = _request_candidates(request_text)

    if echo:
        mentions = [m for m in mentions if not _matches(m, echo, allow_rounded_quotes=allow_rounded_quotes)]

    if not mentions:
        return TraceabilityResult(
            traceable=True,
            numbers_traceable=True,
            from_last_solve=True,
            n_numbers=0,
            n_untraceable=0,
            detail="answer states no numbers of its own",
        )

    untraceable = [
        m
        for m in mentions
        if not _matches(m, list(last) + list(prior), allow_rounded_quotes=allow_rounded_quotes)
    ]
    prior_only = [
        m
        for m in mentions
        if _matches(m, prior, allow_rounded_quotes=allow_rounded_quotes)
        and not _matches(m, last, allow_rounded_quotes=allow_rounded_quotes)
    ]
    last_only = [
        m
        for m in mentions
        if _matches(m, last, allow_rounded_quotes=allow_rounded_quotes)
        and not _matches(m, prior, allow_rounded_quotes=allow_rounded_quotes)
    ]
    # A before/after comparison quotes both, and is not a stale answer.
    quoted_old = bool(prior_only) and not last_only
    numbers_traceable = not untraceable
    from_last_solve = not quoted_old
    detail_parts = []
    if untraceable:
        detail_parts.append(f"{len(untraceable)} of {len(mentions)} number(s) match no tool output")
    if quoted_old:
        detail_parts.append(f"{len(prior_only)} number(s) come only from an earlier solve")
    return TraceabilityResult(
        traceable=numbers_traceable and from_last_solve,
        numbers_traceable=numbers_traceable,
        from_last_solve=from_last_solve,
        n_numbers=len(mentions),
        n_untraceable=len(untraceable),
        untraceable=[m.text for m in untraceable][:20],
        quoted_prior_solve=[m.text for m in prior_only][:20],
        detail="; ".join(detail_parts) or "every number traces to the last solve",
    )


def traceable_answers_rate(results: Iterable[Any]) -> Dict[str, Any]:
    """Share of ANSWERS in which every number traces, as ``{"rate", "count", "total"}``.

    Accepts TraceabilityResult objects or booleans. Per answer, never per number:
    a mean over per-answer number shares would let a few heavily fabricated
    answers barely move the aggregate.
    """
    from evaluation.metrics import rate  # local import: metrics imports nothing from here

    flags = [r.traceable if isinstance(r, TraceabilityResult) else r for r in results]
    return rate(flags)
