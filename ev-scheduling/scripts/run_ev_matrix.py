"""Benchmark matrix for the EV charging case study: every row of the table, every day.

This is the EV counterpart of ``power-flow-agent/scripts/run_pf_matrix.sh`` plus
``power-flow-agent/benchmarks/evaluate_llms.py``, in one Python entry point. It
walks an arm registry over the frozen benchmark days, scores every day with the
same code (``evaluation/outcome.py``), and writes the artefacts a paper table is
built from: per-day rows as CSV and JSONL, a scoreboard, a run manifest, and the
traces each component already writes. ``scripts/ev_report.py`` turns that
directory into ``REPORT.md``.

Why this exists
---------------
``scripts/run_agent_vs_baseline.py`` cannot answer the reviewers. It runs three
phases with different inputs, scores nothing but cost and feasibility, and drops
both LLM arms without failing when ``OPENAI_API_KEY`` is absent (its
``run_phase_agent`` and ``run_phase_baseline`` open with ``if not
os.environ.get("OPENAI_API_KEY"): return None``). With OpenRouter-only
credentials, which is this project's situation, that script writes a results
table containing no LLM at all and looking entirely normal. Three rules follow
from that, and they are the design of this module:

1. **Identical treatment or no run.** Every arm sees the same days, the same
   request objects, the same seeds, the same repeats, and the same completion
   budget. The request list is generated once, hashed, and the digest is stored
   on every row and in the manifest, so a table built from these rows can be
   shown to have compared like with like.
2. **Loud failure.** The run refuses to start when an arm it was asked for
   cannot run (no key for the resolved provider, unknown arm, an arm whose scope
   decision is still open). A day that fails mid-run is written as a row with
   ``status="failed"`` and its error, never omitted, and the process exits
   non-zero.
3. **Two trace destinations.** Traces of a real, paid run are evidence and
   belong in the repository. Traces of a smoke test on synthetic fixture days
   are not evidence and must not land there. ``resolve_out_dir`` enforces that:
   a synthetic run refuses an output directory inside the repository, and its
   scoreboard, report, rows and a sentinel file all say SMOKE TEST.

The twenty benchmark days available today are synthetic fixtures. The real ACN
days are not downloaded (``scripts/freeze_benchmark_days.py`` waits on
``ACN_DATA_API_TOKEN``), so every run launched today is a smoke test and says so
in every artefact it writes.

Arms
----
``optimum`` and ``charge_asap`` are the non-LLM reference rows; ``llm_only`` is
the no-tools arm in two prompting strategies from ``baseline/strategies.py``;
``evagent`` is the solver-grounded arm through ``agent/run.py::run_agent_from_text``.
``react`` and ``plan_act`` are registered as pending: naming one is an error that
says the scope decision is open, rather than a silently missing row.

Usage (from ev-scheduling/):
    python -m scripts.run_ev_matrix --dry-run --days 3
    python -m scripts.run_ev_matrix --days 3 --out-dir /tmp/ev-smoke
    python -m scripts.run_ev_matrix --arm evagent --arm optimum --seeds 0 1
    python -m scripts.run_ev_matrix --days 20 --workers 5   # same rows, less wall time
"""

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import threading
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import date as _date
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.run import AgentResult, ClarificationResult, run_agent_from_text  # noqa: E402
from agent.validate.gate import CONDITION_LABELS, CONDITION_ORDER  # noqa: E402
from baseline import strategies as prompt_strategies  # noqa: E402
from baseline.parse import REPAIR_KINDS, parse_llm_schedule  # noqa: E402
from config.llm import (  # noqa: E402
    ModelSpec,
    RunRecorder,
    RunUsage,
    build_client,
    call_chat,
    missing_key_message,
    parse_model_spec,
    resolve_api_key,
)
from constraints.checker import check  # noqa: E402
from data.benchmark import store  # noqa: E402
from evaluation.formulation import formulation_exact  # noqa: E402
from evaluation.metrics import (  # noqa: E402
    UNMET_TOL_KWH,
    charge_asap_schedule,
    cost_gap,
    peak_load_kw,
    pct_fully_served,
    total_cost,
    total_unmet_kwh,
)
from evaluation.outcome import (  # noqa: E402
    GAP_TOL_PCT,
    SOLVED_TERMS,
    GateVerdict,
    classify_outcome,
)
from evaluation.requests import (  # noqa: E402
    EVRequest,
    build_site_tou,
    capacity_shortfall_indices,
    load_benchmark_requests,
    parse_time_phrase,
    request_answer,
    solve_day,
    to_jsonl,
)
from evaluation.traceability import check_traceability  # noqa: E402
from optimization.solver import solve  # noqa: E402

REPO_ROOT = PROJECT_ROOT.parent

# Shared price book of the repository; the power-flow project holds it next to
# its own runner. Prices are USD per million tokens.
DEFAULT_PRICING_FILE = REPO_ROOT / "power-flow-agent" / "pricing.json"

# Used only when no price book is readable, so a dry run still prints a number.
FALLBACK_PRICING: Dict[str, Dict[str, float]] = {
    "openrouter:openai/gpt-4o": {"input": 2.5, "output": 10.0},
    "openrouter:openai/gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "openai:gpt-4o": {"input": 2.5, "output": 10.0},
    "openai:gpt-4o-mini": {"input": 0.15, "output": 0.6},
}

# Tokens per character, for the offline estimate. Four characters per token is
# the usual English rule of thumb for the OpenAI tokenisers; the dry run prints
# this constant next to the estimate because the estimate is only as good as it.
CHARS_PER_TOKEN = 4.0

DEFAULT_MODEL = "openrouter:openai/gpt-4o"
DEFAULT_SEED = 0
DEFAULT_REPEATS = 1
DEFAULT_WORKERS = 1
DEFAULT_BUDGET_USD = 0.50
DEFAULT_MAX_TOOL_ROUNDS = 1

# Kept identical across every LLM arm; see ``baseline/strategies.py``.
MAX_COMPLETION_TOKENS = prompt_strategies.MAX_COMPLETION_TOKENS

SMOKE_SENTINEL_NAME = "SMOKE_TEST_SYNTHETIC_DO_NOT_CITE.txt"

SMOKE_BANNER = (
    "SMOKE TEST ON SYNTHETIC FIXTURE DAYS. The sessions behind these numbers were "
    "generated by data/benchmark/fixtures_gen.py and were never measured. No number in "
    "this directory may be quoted, plotted, or put in the paper. The real ACN days are "
    "not downloaded yet (scripts/freeze_benchmark_days.py needs ACN_DATA_API_TOKEN)."
)

REAL_BANNER = (
    "Real frozen ACN days. These traces are the evidence behind the reported numbers and "
    "belong in the repository."
)


# --------------------------------------------------------------------------- errors


class HarnessError(RuntimeError):
    """A condition that must stop the run before anything is spent."""


class BudgetExceeded(RuntimeError):
    """The estimated spend passed the ceiling; the remaining rows are not run."""


# --------------------------------------------------------------------------- arms


@dataclass(frozen=True)
class CostModel:
    """Offline estimate of one day-repeat of one arm, for ``--dry-run``.

    Attributes:
        n_calls: Model calls per day-repeat.
        completion_tokens_per_call: Generated tokens assumed per call.
        context_resend_factor: Multiplier on the prompt tokens, because a
            multi-turn arm re-sends the conversation on every call. 1.0 for a
            single-call arm.
        basis: One line naming where the numbers come from, printed by the dry
            run so the estimate can be argued with.
    """

    n_calls: int
    completion_tokens_per_call: int
    context_resend_factor: float = 1.0
    basis: str = ""


ZERO_COST = CostModel(0, 0, 1.0, "no model call")


@dataclass(frozen=True)
class Arm:
    """One row of the results table and everything the harness needs to run it.

    Attributes:
        name: Row name, used on the command line and in every artefact.
        label: Human-readable name for a table.
        uses_llm: True when the arm calls a model, which makes a provider key a
            precondition of starting the run.
        has_gate: True when the arm runs the verification gate, which is what
            makes an escalation possible at all.
        scores_formulation: True when the arm exposes an extracted problem to
            compare with the ground truth. False leaves the term not checkable
            rather than pretending it passed.
        grounded: True when the arm's numbers come from a trusted tool, which is
            what makes traceability a measurement rather than a tautology.
        strategy: Prompting strategy for an ``llm_only`` arm, "" otherwise.
        cost: Offline cost model for the dry run.
        implemented: False for a registered but unbuilt arm.
        pending_reason: Why an unimplemented arm is not runnable.
        description: One line for the report.
    """

    name: str
    label: str
    uses_llm: bool
    has_gate: bool
    scores_formulation: bool
    grounded: bool
    strategy: str = ""
    cost: CostModel = ZERO_COST
    implemented: bool = True
    pending_reason: str = ""
    description: str = ""


ARMS: Dict[str, Arm] = {}


def register_arm(arm: Arm) -> Arm:
    """Add an arm to the registry, replacing any arm of the same name."""
    ARMS[arm.name] = arm
    return arm


register_arm(
    Arm(
        name="optimum",
        label="CVXPY optimum (structured)",
        uses_llm=False,
        has_gate=False,
        scores_formulation=False,
        grounded=True,
        cost=ZERO_COST,
        description=(
            "The LP solved directly on the structured ground-truth day. The reference row: "
            "the cost gap it reports is zero by construction and it never reads the request text."
        ),
    )
)

register_arm(
    Arm(
        name="charge_asap",
        label="Charge as soon as possible (rule)",
        uses_llm=False,
        has_gate=False,
        scores_formulation=False,
        grounded=True,
        cost=ZERO_COST,
        description=(
            "evaluation/metrics.py::charge_asap_schedule, the uncontrolled rule the paper has "
            "always used as the cost-reduction denominator and has never scored as a row."
        ),
    )
)

register_arm(
    Arm(
        name="llm_only:structured",
        label="LLM-only, structured prompting",
        uses_llm=True,
        has_gate=False,
        scores_formulation=False,
        grounded=False,
        strategy="structured",
        cost=CostModel(
            n_calls=1,
            completion_tokens_per_call=2200,
            context_resend_factor=1.0,
            basis=(
                "one call; prompt measured offline from baseline/strategies.py::build_messages; "
                "completion assumed 2200 tokens, about n_sessions x n_steps numbers at 4 decimals"
            ),
        ),
        description="No tools. The schedule and the answer are generated as text.",
    )
)

register_arm(
    Arm(
        name="llm_only:chain_of_thought",
        label="LLM-only, chain-of-thought prompting",
        uses_llm=True,
        has_gate=False,
        scores_formulation=False,
        grounded=False,
        strategy="chain_of_thought",
        cost=CostModel(
            n_calls=1,
            completion_tokens_per_call=3200,
            context_resend_factor=1.0,
            basis=(
                "one call; prompt measured offline; completion assumed 3200 tokens, the "
                "structured arm's schedule plus the reasoning the strategy asks for"
            ),
        ),
        description="Same input and budget as the structured arm, plus a reasoning section.",
    )
)

register_arm(
    Arm(
        name="evagent",
        label="EVAgent (solver-grounded, gated)",
        uses_llm=True,
        has_gate=True,
        scores_formulation=True,
        grounded=True,
        cost=CostModel(
            n_calls=4,
            completion_tokens_per_call=700,
            context_resend_factor=2.0,
            basis=(
                "parse call, one tool-calling round, one explanation turn, and one gate retry "
                "budgeted; prompt measured offline from the parse system prompt and "
                "baseline/prompt.py::build_prompt_for_agent; the conversation is re-sent every "
                "turn, so prompt tokens are doubled"
            ),
        ),
        description=(
            "agent/run.py::run_agent_from_text: parse the request text, call the CVXPY tool, "
            "answer behind the five-condition verification gate."
        ),
    )
)

register_arm(
    Arm(
        name="react",
        label="ReAct (pending)",
        uses_llm=True,
        has_gate=False,
        scores_formulation=True,
        grounded=True,
        implemented=False,
        pending_reason=(
            "the ReAct row is waiting on a scope decision that is not the harness's to take "
            "(notes repo, diseno_comparacion_pfagent.md section 8). Registered here so naming it "
            "is an error rather than a silently absent row."
        ),
        description="Registered, not implemented.",
    )
)

register_arm(
    Arm(
        name="plan_act",
        label="Plan-and-Act (pending)",
        uses_llm=True,
        has_gate=False,
        scores_formulation=True,
        grounded=True,
        implemented=False,
        pending_reason=(
            "the Plan-and-Act row is waiting on the same scope decision as ReAct. Registered "
            "here so naming it is an error rather than a silently absent row."
        ),
        description="Registered, not implemented.",
    )
)

DEFAULT_ARMS: Tuple[str, ...] = (
    "optimum",
    "charge_asap",
    "llm_only:structured",
    "llm_only:chain_of_thought",
    "evagent",
)


def resolve_arms(names: Optional[Sequence[str]]) -> List[Arm]:
    """Resolve arm names to Arm objects, refusing anything that cannot be run.

    Args:
        names: Arm names from the command line, or None for ``DEFAULT_ARMS``.

    Returns:
        The arms, in the order given.

    Raises:
        HarnessError: If a name is unknown or names an arm that is registered
            but not implemented. Both are refusals, not warnings: an arm that
            silently vanishes from the table is the defect this harness exists
            to prevent.
    """
    wanted = list(names) if names else list(DEFAULT_ARMS)
    out: List[Arm] = []
    for name in wanted:
        arm = ARMS.get(name)
        if arm is None:
            raise HarnessError(
                f"unknown arm {name!r}. Registered arms: {', '.join(sorted(ARMS))}"
            )
        if not arm.implemented:
            raise HarnessError(f"arm {name!r} is not implemented: {arm.pending_reason}")
        out.append(arm)
    return out


# --------------------------------------------------------------------------- budget


@dataclass
class Reservation:
    """One item's claim on the budget, held while that item is in flight.

    Adding a cost once an item has finished is enough when items run one at a
    time, and wrong as soon as they do not: with ``N`` items in flight the run
    can pass the ceiling by ``N`` items' worth of spend before anything notices.
    A reservation is taken before an item is launched and released when it
    returns, and while it is open the ledger counts the larger of the estimate
    and what the item has really spent so far.

    Attributes:
        item_id: The item this was taken for, named in the refusal message.
        est_usd: What the item was estimated to cost, reserved at launch.
        actual_usd: What it has cost so far, as its own calls report back.
    """

    item_id: str
    est_usd: float
    actual_usd: float = 0.0

    @property
    def outstanding_usd(self) -> float:
        """The part of the estimate that has not become real spend yet."""
        return max(0.0, float(self.est_usd) - float(self.actual_usd))


@dataclass
class Ledger:
    """Running token and USD accounting, with a ceiling that stops the run.

    Safe to share across threads: every mutation and every ceiling test is taken
    under one lock, so the check and the claim that follows it cannot be split
    by another worker.

    Attributes:
        price_in: USD per million prompt tokens.
        price_out: USD per million completion tokens.
        limit_usd: Ceiling. The run stops before the call that would pass it.
        prompt_tokens, completion_tokens: Totals actually reported by the
            provider.
        spent_usd: Totals priced with ``price_in`` / ``price_out``.
        n_calls: Model calls made.
    """

    price_in: float = 0.0
    price_out: float = 0.0
    limit_usd: float = DEFAULT_BUDGET_USD
    prompt_tokens: int = 0
    completion_tokens: int = 0
    spent_usd: float = 0.0
    n_calls: int = 0
    _lock: Any = field(default_factory=threading.RLock, repr=False, compare=False)
    _open: List[Reservation] = field(default_factory=list, repr=False, compare=False)

    def price(self, prompt_tokens: int, completion_tokens: int) -> float:
        """USD for a given number of tokens at this ledger's prices."""
        return (
            prompt_tokens / 1e6 * float(self.price_in)
            + completion_tokens / 1e6 * float(self.price_out)
        )

    def add(self, prompt_tokens: int, completion_tokens: int,
            reservation: Optional[Reservation] = None) -> float:
        """Record one call's tokens and return what it cost.

        Args:
            prompt_tokens, completion_tokens: As the provider reported them.
            reservation: The claim of the item the call belongs to, so the
                estimate is reconciled with the real cost while the item is
                still running rather than only when it ends.
        """
        usd = self.price(int(prompt_tokens), int(completion_tokens))
        with self._lock:
            self.n_calls += 1
            self.prompt_tokens += int(prompt_tokens)
            self.completion_tokens += int(completion_tokens)
            self.spent_usd += usd
            if reservation is not None:
                reservation.actual_usd = float(reservation.actual_usd) + usd
        return usd

    def committed_usd(self) -> float:
        """Spend so far plus the unspent part of every open reservation."""
        with self._lock:
            return self.spent_usd + sum(r.outstanding_usd for r in self._open)

    def reserve(self, item_id: str, est_usd: float) -> Reservation:
        """Claim an item's estimated cost, or refuse to let it be launched.

        Args:
            item_id: The item being launched.
            est_usd: What it is estimated to cost, from ``estimate_item_cost``.

        Returns:
            The open reservation, to be released when the item returns.

        Raises:
            BudgetExceeded: When the claim would put the run at or over the
                ceiling. Nothing is reserved and the item must not be launched.
        """
        claim = max(0.0, float(est_usd))
        with self._lock:
            committed = self.spent_usd + sum(r.outstanding_usd for r in self._open)
            if self.limit_usd is not None and committed + claim >= float(self.limit_usd):
                raise BudgetExceeded(
                    f"budget ceiling would be passed by {item_id}: "
                    f"${committed:.4f} committed plus ${claim:.4f} estimated "
                    f"of ${float(self.limit_usd):.2f}"
                )
            reservation = Reservation(item_id=item_id, est_usd=claim)
            self._open.append(reservation)
            return reservation

    def release(self, reservation: Optional[Reservation]) -> float:
        """Close a finished item's claim and return what it really cost."""
        if reservation is None:
            return 0.0
        with self._lock:
            for position, open_claim in enumerate(self._open):
                if open_claim is reservation:
                    del self._open[position]
                    break
            return float(reservation.actual_usd)

    def guard(self) -> None:
        """Stop before a call when the ceiling is already reached.

        Raises:
            BudgetExceeded: When the spend so far is at or above the ceiling.
        """
        with self._lock:
            if self.limit_usd is not None and self.spent_usd >= float(self.limit_usd):
                raise BudgetExceeded(
                    f"budget ceiling reached: ${self.spent_usd:.4f} spent of ${self.limit_usd:.2f}"
                )


# --------------------------------------------------------------------------- client proxy


class _Completions:
    """The ``chat.completions`` half of the proxy."""

    def __init__(self, owner: "RecordingClient") -> None:
        self._owner = owner

    def create(self, **kwargs: Any) -> Any:
        """Forward one call, after the budget guard and the shared token cap."""
        return self._owner.create(**kwargs)


class _Chat:
    """The ``chat`` half of the proxy."""

    def __init__(self, owner: "RecordingClient") -> None:
        self.completions = _Completions(owner)


class RecordingClient:
    """A client wrapper that records what was sent and what the provider answered.

    Every entry point in this project accepts a pre-built ``client``, so wrapping
    one is how the harness gets three things it cannot get otherwise, without
    editing any module it does not own:

    * the **resolved** model identifier, read off each response, rather than the
      alias that was requested,
    * a hash of the **prompt actually sent**, taken from the messages payload at
      the moment of the call,
    * one completion budget and one budget ceiling applied to every arm alike.

    Attributes:
        inner: The real client, or a stub in tests.
        max_completion_tokens: Injected as ``max_tokens`` when the caller set
            none, so no arm is allowed to write more than another.
        ledger: Budget accounting, shared across arms.
        reservation: This item's claim on the budget, so every call reconciles
            the estimate reserved at launch with what was really spent.
        calls: One record per call: model asked, model answered, tokens, hash.
    """

    def __init__(
        self,
        inner: Any,
        *,
        max_completion_tokens: int = MAX_COMPLETION_TOKENS,
        ledger: Optional[Ledger] = None,
        reservation: Optional[Reservation] = None,
    ) -> None:
        self.inner = inner
        self.max_completion_tokens = int(max_completion_tokens)
        self.ledger = ledger if ledger is not None else Ledger(limit_usd=float("inf"))
        self.reservation = reservation
        self.calls: List[Dict[str, Any]] = []
        self.chat = _Chat(self)

    def create(self, **kwargs: Any) -> Any:
        """Issue one call and record it.

        Raises:
            BudgetExceeded: Before the call, when the ceiling is already reached.
        """
        if (
            self.max_completion_tokens
            and "max_tokens" not in kwargs
            and "max_completion_tokens" not in kwargs
        ):
            kwargs["max_tokens"] = self.max_completion_tokens
        self.ledger.guard()
        messages = kwargs.get("messages") or []
        response = self.inner.chat.completions.create(**kwargs)
        counts = _token_counts(response)
        self.ledger.add(counts[0], counts[1], reservation=self.reservation)
        self.calls.append(
            {
                "model_requested": kwargs.get("model"),
                "model_resolved": _response_model(response),
                "messages_hash": sha256_json(messages),
                "system_hash": sha256_text(_first_system(messages)),
                "prompt_tokens": counts[0],
                "completion_tokens": counts[1],
                "n_messages": len(messages),
                "max_tokens": kwargs.get("max_tokens"),
                "temperature": kwargs.get("temperature"),
            }
        )
        return response

    # -- what the harness reads back ---------------------------------------

    def resolved_model(self, fallback: str = "") -> str:
        """The model id the provider reported, or ``fallback`` if it reported none.

        The last call wins; every call of one day-repeat goes to the same model.
        """
        for record in reversed(self.calls):
            if record.get("model_resolved"):
                return str(record["model_resolved"])
        return fallback

    def prompt_hash(self) -> str:
        """Hash over every messages payload sent, in order."""
        return sha256_json([c["messages_hash"] for c in self.calls])

    def system_prompt_hash(self) -> str:
        """Hash of the first system message sent."""
        return self.calls[0]["system_hash"] if self.calls else ""


def _response_model(response: Any) -> str:
    """The ``model`` field of a chat-completions response, or ""."""
    value = getattr(response, "model", None)
    if value is None and isinstance(response, dict):
        value = response.get("model")
    return str(value) if value else ""


def _token_counts(response: Any) -> Tuple[int, int]:
    """(prompt_tokens, completion_tokens) of a response; zeros when unreported."""
    from config.llm import extract_token_counts

    counts = extract_token_counts(response)
    return int(counts["prompt_tokens"] or 0), int(counts["completion_tokens"] or 0)


def _first_system(messages: Sequence[Any]) -> str:
    """Content of the first system message of a payload, or ""."""
    for message in messages or []:
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
        if role == "system":
            content = (
                message.get("content")
                if isinstance(message, dict)
                else getattr(message, "content", "")
            )
            return str(content or "")
    return ""


def sha256_text(text: str) -> str:
    """``sha256:<hex>`` of a string, the same shape as the benchmark store's hashes."""
    return "sha256:" + hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def sha256_json(obj: Any) -> str:
    """``sha256:<hex>`` over the canonical JSON of an object."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """Offline token estimate of a string at ``CHARS_PER_TOKEN`` characters per token."""
    return int(round(len(str(text)) / CHARS_PER_TOKEN))


# --------------------------------------------------------------------------- arm output


@dataclass
class ArmOutput:
    """What one arm produced on one day, before any of it is scored.

    Every arm fills the same object, so ``score_row`` is one function and no arm
    is scored by code of its own.

    Attributes:
        schedule: Power schedule, shape (n_sessions, n_steps) in kW, rows in the
            order of the request's own day.
        answer_text: The text the answer is extracted from. For a non-LLM arm
            this is written by ``mechanical_answer_text`` from the arm's own
            schedule; that is what makes the two reference rows comparable
            without giving them the ground-truth answer.
        tool_outputs: Outputs of the last solve, for traceability and the gate.
        prior_tool_outputs: Outputs of earlier solves in the same episode.
        parsed_problem: The extracted problem, for the formulation term; None
            for an arm with no extraction step.
        gate: The verification gate's verdict; None for an arm with no gate.
        gate_row: The gate's per-condition row.
        usage: Token accounting of the whole day-repeat.
        model_resolved: The model id the provider reported.
        prompt_hash, system_prompt_hash: Hashes of what was actually sent.
        trace_path, parse_trace_path: Where the component wrote its trace.
        repairs: ``RepairLog.to_dict()`` of the schedule parse, or None when the
            arm's schedule came from the solver and needed no parsing.
        parse_success: Whether the reply parsed into a schedule; None when there
            was no text schedule to parse.
        notes: Anything the report should say about this day.
    """

    schedule: np.ndarray
    answer_text: str = ""
    tool_outputs: List[Any] = field(default_factory=list)
    prior_tool_outputs: List[Any] = field(default_factory=list)
    parsed_problem: Any = None
    gate: Optional[GateVerdict] = None
    gate_row: Dict[str, Any] = field(default_factory=dict)
    usage: RunUsage = field(default_factory=RunUsage)
    model_resolved: str = ""
    prompt_hash: str = ""
    system_prompt_hash: str = ""
    trace_path: Optional[Path] = None
    parse_trace_path: Optional[Path] = None
    repairs: Optional[Dict[str, Any]] = None
    parse_success: Optional[bool] = None
    notes: str = ""


@dataclass
class RunContext:
    """Everything one day-repeat of one arm is run with.

    Identical for every arm but ``arm`` itself: same request, same seed, same
    repeat, same model, same completion budget, same trace root.
    """

    arm: Arm
    request: EVRequest
    seed: int
    repeat: int
    spec: ModelSpec
    model_requested: str
    trace_dir: Path
    run_id: str
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS
    max_completion_tokens: int = MAX_COMPLETION_TOKENS
    client: Optional[RecordingClient] = None
    write_trace: bool = True


# --------------------------------------------------------------------------- rule answers


def mechanical_answer_text(request: EVRequest, schedule: np.ndarray) -> str:
    """The answer a non-LLM arm gives, computed from its own schedule and day.

    The two reference rows produce a schedule and no prose, but Solved is a
    conjunction that includes the answer to the question asked, so a row with no
    answer would score wrong for a reason that says nothing about the arm. This
    writes the answer each variant asks for, from the arm's **own** output and
    never from ``request.truth``, and phrases it so that
    ``evaluation/requests.py::extract_answer`` reads it back. A rule arm can
    therefore be wrong: ``charge_asap`` answers its own cost, which is not the
    cheapest plan's cost, and the answer term marks it wrong, correctly.

    What this measures is a formula written here, not a system's reading of the
    request, and the report says so next to the two reference rows.

    Args:
        request: The request being answered.
        schedule: The arm's schedule, rows parallel to ``request.day.sessions``.

    Returns:
        The answer text. A short state summary for a variant that asks nothing.
    """
    day = request.day
    dt = day.dt_hours
    site, tou = build_site_tou(request)
    cost = float(total_cost(schedule, tou, dt))
    unmet = float(total_unmet_kwh(schedule, day, dt))
    if unmet < UNMET_TOL_KWH:
        unmet = 0.0
    requested = float(sum(s.energy_kwh for s in day.sessions))
    pct = 100.0 * (requested - unmet) / requested if requested > 0 else 0.0
    variant = request.variant

    if variant == "cost_question":
        return f"{prompt_strategies.ANSWER_PREFIX} ${cost:.2f}"
    if variant == "unmet_question":
        return f"{prompt_strategies.ANSWER_PREFIX} {unmet:.2f} kWh undelivered"
    if variant == "served_share":
        return f"{prompt_strategies.ANSWER_PREFIX} {pct:.2f} percent of the requested energy is delivered"
    if variant == "feasible_yesno":
        verdict = "yes" if unmet <= UNMET_TOL_KWH else "no"
        return f"{prompt_strategies.ANSWER_PREFIX} {verdict}"
    if variant == "total_energy_requested":
        return f"{prompt_strategies.ANSWER_PREFIX} {requested:.2f} kWh"
    if variant == "cars_plugged_in_at":
        hours = parse_time_phrase(request.question or "")
        if hours is None:
            return "The question names a time this rule arm could not read."
        step = int(round(float(hours) / dt))
        n = sum(1 for s in day.sessions if s.arrival_idx <= step < s.departure_idx)
        return f"{prompt_strategies.ANSWER_PREFIX} {n}"
    if variant == "largest_request_car":
        if not day.sessions:
            return "There are no cars."
        top = max(range(len(day.sessions)), key=lambda i: day.sessions[i].energy_kwh)
        return f"The largest energy request is {request.labels[top]}."
    if variant == "capacity_shortfall_cars":
        idx = capacity_shortfall_indices(day)
        if not idx:
            return "Every car can be filled by its own charger in the time it is parked."
        named = ", ".join(request.labels[i] for i in idx)
        return f"These cars cannot be fully served by their own charger: {named}."
    return (
        f"The schedule costs ${cost:.2f}, peaks at {float(peak_load_kw(schedule)):.2f} kW, "
        f"and leaves {unmet:.2f} kWh undelivered."
    )


def _solve_tool_output(request: EVRequest, schedule: np.ndarray) -> Dict[str, Any]:
    """The headline metrics of a schedule, in the shape the solver tool returns them."""
    day = request.day
    site, tou = build_site_tou(request)
    return {
        "total_cost_usd": round(float(total_cost(schedule, tou, day.dt_hours)), 4),
        "peak_load_kw": round(float(peak_load_kw(schedule)), 4),
        "total_unmet_kwh": round(float(total_unmet_kwh(schedule, day, day.dt_hours)), 4),
        "pct_fully_served": round(float(pct_fully_served(schedule, day, day.dt_hours)), 4),
    }


# --------------------------------------------------------------------------- runners


def run_optimum(ctx: RunContext) -> ArmOutput:
    """The CVXPY optimum on the structured ground-truth day.

    Raises:
        HarnessError: If the LP does not solve, which leaves the row with no
            schedule. It is raised rather than returned as zeros so the day is
            written as a failed row instead of as a very bad one.
    """
    request = ctx.request
    site, tou = build_site_tou(request)
    started = time.time()
    result = solve(request.day, site, tou)
    if not result.success:
        raise HarnessError(f"the CVXPY solver returned {result.message!r}")
    usage = RunUsage(wall_time_s=time.time() - started)
    schedule = np.asarray(result.schedule, dtype=float)
    return ArmOutput(
        schedule=schedule,
        answer_text=mechanical_answer_text(request, schedule),
        tool_outputs=[_solve_tool_output(request, schedule)],
        usage=usage,
        model_resolved="",  # no model answered; the arm column says what produced this
        notes="LP solved on the structured day; the request text is not read",
    )


def run_charge_asap(ctx: RunContext) -> ArmOutput:
    """The uncontrolled rule: every car charges at full power from arrival."""
    request = ctx.request
    site, _tou = build_site_tou(request)
    started = time.time()
    schedule = charge_asap_schedule(request.day, float(site.get_P_max_at_step(0)))
    usage = RunUsage(wall_time_s=time.time() - started)
    return ArmOutput(
        schedule=np.asarray(schedule, dtype=float),
        answer_text=mechanical_answer_text(request, schedule),
        tool_outputs=[_solve_tool_output(request, schedule)],
        usage=usage,
        model_resolved="",  # no model answered; the arm column says what produced this
        notes="charge_asap_schedule; the site cap is not enforced by the rule",
    )


def run_llm_only(ctx: RunContext) -> ArmOutput:
    """The no-tools arm: one call, the strategy's prompt, the reply parsed.

    The call goes through ``config.llm.call_chat`` and a ``RunRecorder``, so the
    trace is written exactly as the other arms' traces are. No tools are
    attached, by the contract in ``baseline/strategies.py``.

    Raises:
        HarnessError: If the provider returns no choices, which is a failed row
            and not an empty schedule.
    """
    request = ctx.request
    arm = ctx.arm
    client = ctx.client
    if client is None:
        raise HarnessError("run_llm_only needs a client; preflight should have built one")

    messages = prompt_strategies.build_messages(arm.strategy, request)
    recorder = RunRecorder(
        spec=ctx.spec,
        arm=f"llm_only_{arm.strategy}",
        run_id=ctx.run_id,
        request=request.text,
    )
    completion = call_chat(
        client,
        recorder,
        model=ctx.spec.model,
        messages=messages,
        max_tokens=ctx.max_completion_tokens,
        temperature=0.0,
    )
    choices = getattr(completion, "choices", None) or []
    if not choices:
        recorder.finish(messages=messages, final_text="", status="empty_response",
                        error="the provider returned no choices")
        if ctx.write_trace:
            recorder.write(ctx.trace_dir)
        raise HarnessError(f"the {ctx.spec.provider} API returned no choices")

    reply = choices[0].message.content or ""
    parse_result = parse_llm_schedule(reply, request.day)
    usage = recorder.finish(
        messages=list(messages) + [{"role": "assistant", "content": reply}],
        final_text=reply,
        status="ok" if parse_result.success else "parse_failed",
        error=parse_result.error_message,
    )
    trace_path = recorder.write(ctx.trace_dir) if ctx.write_trace else None
    return ArmOutput(
        schedule=np.asarray(parse_result.schedule, dtype=float),
        answer_text=reply,
        tool_outputs=[],
        usage=usage,
        model_resolved=client.resolved_model(ctx.spec.key),
        prompt_hash=client.prompt_hash(),
        system_prompt_hash=client.system_prompt_hash(),
        trace_path=trace_path,
        repairs=parse_result.repairs.to_dict(),
        parse_success=bool(parse_result.success),
        notes=parse_result.error_message or "",
    )


def run_evagent(ctx: RunContext) -> ArmOutput:
    """The solver-grounded arm, through ``agent/run.py::run_agent_from_text``.

    Raises:
        HarnessError: When the parse asks for clarification. That is a real
            outcome of the arm, but it produces no schedule and no answer, so it
            is written as a failed row with the question it asked, not as a
            silently empty one.
    """
    request = ctx.request
    result = run_agent_from_text(
        request.text,
        model=ctx.model_requested,
        max_retries=ctx.max_tool_rounds,
        client=ctx.client,
        run_id=ctx.run_id,
        trace_dir=ctx.trace_dir,
        write_trace=ctx.write_trace,
    )
    client = ctx.client
    resolved = client.resolved_model(ctx.spec.key) if client is not None else ctx.spec.key
    prompt_hash = client.prompt_hash() if client is not None else ""
    system_hash = client.system_prompt_hash() if client is not None else ""

    if isinstance(result, ClarificationResult):
        raise HarnessError(
            "the parse asked for clarification instead of producing a schedule: "
            f"{result.message[:200]}"
        )

    tool_outputs = list(result.tool_outputs or [])
    last = tool_outputs[-1:] if tool_outputs else []
    prior = tool_outputs[:-1] if len(tool_outputs) > 1 else []
    schedule = _align_rows(np.asarray(result.schedule, dtype=float), len(request.day.sessions))
    return ArmOutput(
        schedule=schedule,
        answer_text=result.explanation or "",
        tool_outputs=last,
        prior_tool_outputs=prior,
        parsed_problem=result.parsed_problem,
        gate=result.gate,
        gate_row=dict(result.gate_row or {}),
        usage=result.total_usage(),
        model_resolved=resolved,
        prompt_hash=prompt_hash,
        system_prompt_hash=system_hash,
        trace_path=result.trace_path,
        parse_trace_path=result.parse_trace_path,
        notes="declared failure" if result.declared_failure else "",
    )


RUNNERS: Dict[str, Callable[[RunContext], ArmOutput]] = {
    "optimum": run_optimum,
    "charge_asap": run_charge_asap,
    "llm_only:structured": run_llm_only,
    "llm_only:chain_of_thought": run_llm_only,
    "evagent": run_evagent,
}


def _align_rows(schedule: np.ndarray, n_sessions: int) -> np.ndarray:
    """Make a schedule's row count match the ground-truth day's.

    An arm whose extraction dropped or invented a car returns a schedule of the
    wrong height. Rows are matched positionally and the remainder zero-filled,
    so the state term is evaluated on what the arm would actually run for the
    real cars. The formulation term is what records that a car was dropped; this
    only stops the shape mismatch from crashing the checker.
    """
    array = np.atleast_2d(np.asarray(schedule, dtype=float))
    if array.shape[0] == n_sessions:
        return array
    out = np.zeros((n_sessions, array.shape[1]), dtype=float)
    keep = min(n_sessions, array.shape[0])
    if keep:
        out[:keep, :] = array[:keep, :]
    return out


# --------------------------------------------------------------------------- scoring

# Traceability policies. "grounded_only" measures the term for arms whose answer
# text was written by a model from a real tool output, which today is EVAgent
# alone: an arm with no tool has nothing for its numbers to trace to, and scoring
# it as untraceable would report a definition rather than a measurement. "all"
# measures it for every LLM arm, which fails the no-tools arm by construction.
# Whichever is chosen is recorded on every row, and the rows carry the answer
# text and the tool outputs, so the other policy can be applied later without
# re-running anything.
TRACEABILITY_POLICIES: Tuple[str, ...] = ("grounded_only", "all")

# How the Formulation column is aggregated, recorded in the manifest. "per_session"
# is the supplement's Table S3 definition; the day verdict is kept beside it as
# ``formulation_days``.
FORMULATION_AGGREGATION = "per_session"

# The gate's per-condition columns, derived from the gate itself so the two
# cannot drift apart.
GATE_ROW_FIELDS: Tuple[str, ...] = tuple(
    field_name
    for name in CONDITION_ORDER
    for field_name in (f"gate_{CONDITION_LABELS[name]}_{name}", f"gate_{CONDITION_LABELS[name]}_residual")
)

REPAIR_ROW_FIELDS: Tuple[str, ...] = tuple(f"repair_{kind}" for kind in REPAIR_KINDS)

ROW_FIELDS: Tuple[str, ...] = (
    # identity of the item
    "run_id", "arm", "arm_label", "date", "site_id", "seed", "repeat",
    "request_id", "variant", "answer_kind", "requests_digest",
    # provenance of the data
    "synthetic", "data_source", "smoke_test",
    # what was actually sent, and to what
    "model_requested", "model_spec", "model_resolved",
    "system_prompt_hash", "prompt_hash", "strategy", "max_completion_tokens",
    "max_tool_rounds", "traceability_policy",
    # did it run
    "status", "error",
    # the outcome split
    "outcome", "solved", "escalated", "wrong_unflagged", "outcome_reason",
    # every term of the conjunction
    "formulation_status", "formulation_error_type",
    "n_sessions_exact", "n_sessions_truth", "n_sessions_parsed",
    "state_status", "no_hard_violation", "max_violation_kw",
    "gap_pct", "gap_comparable", "gap_tol_pct",
    "traceability_status", "n_numbers", "n_untraceable",
    "answer_status", "answer_truth", "answer_given", "answer_tolerance",
    # the physical quantities behind the table
    "cost_usd", "cost_star_usd", "unmet_kwh", "unmet_star_kwh",
    "peak_kw", "pct_fully_served", "n_sessions", "n_schedule_rows",
    # the gate
    "gate_passed", "gate_declared_failure", "gate_reason",
) + GATE_ROW_FIELDS + (
    # what the reply cost to make scorable
    "parse_success", "repairs_changed", "repair_negative_cells",
    "repair_cells_changed", "repair_rows_changed",
) + REPAIR_ROW_FIELDS + (
    # budget
    "prompt_tokens", "completion_tokens", "total_tokens", "n_llm_calls",
    "n_tool_calls", "n_missing_usage", "est_cost_usd", "wall_s",
    # where the evidence is
    "trace_path", "parse_trace_path", "answer_text",
)

# The answer text is kept in full in the JSONL and truncated in the CSV, which a
# spreadsheet has to be able to open.
CSV_TEXT_CHARS = 400


def _jsonable(value: Any) -> Any:
    """Plain-Python form of a value, for a JSON row."""
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


def score_row(
    ctx: RunContext,
    out: ArmOutput,
    *,
    traceability_policy: str = "grounded_only",
    gap_tol_pct: float = GAP_TOL_PCT,
) -> Dict[str, Any]:
    """Score one day-repeat of one arm. One function, every arm.

    Every term is evaluated and stored, including both answers on every day.
    A request that only prescribes an operation still records the ground-truth
    state summary and whatever the system said, because the power-flow study
    discarded that value and then could not size a scoring defect without
    re-running the whole matrix.

    Args:
        ctx: The context the arm was run with.
        out: What the arm produced.
        traceability_policy: One of ``TRACEABILITY_POLICIES``.
        gap_tol_pct: Two-sided cost-gap tolerance, per cent.

    Returns:
        The scored fields of the row, ready to be merged into a full row.
    """
    request = ctx.request
    day = request.day
    site, tou = build_site_tou(request)

    check_result = check(out.schedule, day, site)
    optimum = solve_day(
        day,
        site_cap_kw=request.site_cap_kw,
        peak_price=request.peak_price,
        off_peak_price=request.off_peak_price,
    )
    cost_usd = float(total_cost(out.schedule, tou, day.dt_hours))
    unmet_kwh = float(total_unmet_kwh(out.schedule, day, day.dt_hours))
    gap = cost_gap(
        cost_usd,
        optimum.cost_usd,
        unmet_kwh=unmet_kwh,
        unmet_star_kwh=optimum.unmet_kwh,
    )

    formulation = None
    formulation_error_type = ""
    n_sessions_exact: Optional[int] = None
    n_sessions_truth: Optional[int] = None
    n_sessions_parsed: Optional[int] = None
    if ctx.arm.scores_formulation and out.parsed_problem is not None:
        result = formulation_exact(out.parsed_problem, day, dt_hours=day.dt_hours)
        formulation = bool(result.formulation_exact)
        formulation_error_type = result.formulation_error_type
        # Numerator and denominator of the per-session Formulation rate, kept per
        # day so the column can be re-aggregated from committed rows.
        n_sessions_exact = result.n_sessions_exact
        n_sessions_truth = result.n_truth
        n_sessions_parsed = result.n_parsed

    measure_traceability = ctx.arm.uses_llm and (
        traceability_policy == "all" or (traceability_policy == "grounded_only" and ctx.arm.grounded)
    )
    traceable: Optional[bool] = None
    n_numbers: Optional[int] = None
    n_untraceable: Optional[int] = None
    if measure_traceability:
        trace_result = check_traceability(
            out.answer_text,
            out.tool_outputs,
            prior_tool_outputs=out.prior_tool_outputs,
            request_text=request.text,
        )
        traceable = bool(trace_result.traceable)
        n_numbers = int(trace_result.n_numbers)
        n_untraceable = int(trace_result.n_untraceable)

    answer = request_answer(request, out.answer_text)
    outcome = classify_outcome(
        formulation_exact=formulation,
        no_hard_violation=bool(check_result.no_hard_violation),
        gap_pct=gap.gap_pct,
        traceable=traceable,
        gate=out.gate,
        answer=answer,
        gap_comparable=gap.comparable,
        max_violation_kw=float(check_result.max_violation_kw),
        gap_tol_pct=gap_tol_pct,
    )
    scored = dict(outcome.as_row())
    scored.update(
        {
            "outcome_reason": scored.pop("reason", ""),
            "formulation_error_type": formulation_error_type,
            "n_sessions_exact": n_sessions_exact,
            "n_sessions_truth": n_sessions_truth,
            "n_sessions_parsed": n_sessions_parsed,
            "n_numbers": n_numbers,
            "n_untraceable": n_untraceable,
            "answer_tolerance": answer.tolerance,
            "cost_usd": round(cost_usd, 6),
            "cost_star_usd": round(float(optimum.cost_usd), 6),
            "unmet_kwh": round(unmet_kwh, 6),
            "unmet_star_kwh": round(float(optimum.unmet_kwh), 6),
            "peak_kw": round(float(peak_load_kw(out.schedule)), 6),
            "pct_fully_served": round(float(pct_fully_served(out.schedule, day, day.dt_hours)), 4),
            "n_sessions": len(day.sessions),
            "n_schedule_rows": int(np.atleast_2d(out.schedule).shape[0]),
            "gap_tol_pct": gap_tol_pct,
            "traceability_policy": traceability_policy,
        }
    )
    scored.pop("detail", None)
    return scored


def build_row(
    ctx: RunContext,
    out: Optional[ArmOutput],
    scored: Optional[Dict[str, Any]],
    *,
    status: str,
    error: str = "",
    requests_digest: str = "",
    synthetic: bool = True,
    data_source: str = "",
    est_cost_usd: float = 0.0,
    traceability_policy: str = "grounded_only",
) -> Dict[str, Any]:
    """Assemble one full row, whether the arm succeeded or failed.

    A failed arm still produces a row: its identity, what it was asked to do,
    the ground-truth answer, and why it failed. Omitting it is what would let a
    reader mistake a broken arm for a missing one.

    Args:
        ctx: The context the arm ran in.
        out: What the arm produced, or None when it raised.
        scored: The scored fields, or None when there was nothing to score.
        status: "ok", "failed", or "over_budget".
        error: The failure text, empty on success.
        requests_digest: Digest of the request list every arm shared.
        synthetic: Whether the day's sessions are generated fixtures.
        data_source: The loader source the days came from.
        est_cost_usd: USD this row cost, priced from the reported tokens.
        traceability_policy: Policy in force for this run.

    Returns:
        A dict with exactly the keys of ``ROW_FIELDS``.
    """
    request = ctx.request
    usage = out.usage if out is not None else RunUsage()
    row: Dict[str, Any] = {name: None for name in ROW_FIELDS}
    row.update(
        {
            "run_id": ctx.run_id,
            "arm": ctx.arm.name,
            "arm_label": ctx.arm.label,
            "date": request.date,
            "site_id": request.site_id,
            "seed": ctx.seed,
            "repeat": ctx.repeat,
            "request_id": request.id,
            "variant": request.variant,
            "answer_kind": request.kind,
            "requests_digest": requests_digest,
            "synthetic": bool(synthetic),
            "data_source": data_source,
            "smoke_test": bool(synthetic),
            "model_requested": ctx.model_requested,
            "model_spec": ctx.spec.key,
            "model_resolved": (out.model_resolved if out is not None else ""),
            "system_prompt_hash": (out.system_prompt_hash if out is not None else ""),
            "prompt_hash": (out.prompt_hash if out is not None else ""),
            "strategy": ctx.arm.strategy,
            "max_completion_tokens": ctx.max_completion_tokens if ctx.arm.uses_llm else None,
            "max_tool_rounds": ctx.max_tool_rounds if ctx.arm.uses_llm else None,
            "traceability_policy": traceability_policy,
            "status": status,
            "error": error,
            # Both answers on every row, including a request that asks nothing.
            "answer_truth": _jsonable(request.truth),
            "answer_given": None,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "n_llm_calls": usage.n_llm_calls,
            "n_tool_calls": usage.n_tool_calls,
            "n_missing_usage": usage.n_missing_usage,
            "est_cost_usd": round(float(est_cost_usd), 6),
            "wall_s": round(float(usage.wall_time_s), 4),
            "trace_path": str(out.trace_path) if out is not None and out.trace_path else "",
            "parse_trace_path": (
                str(out.parse_trace_path) if out is not None and out.parse_trace_path else ""
            ),
            "answer_text": (out.answer_text if out is not None else ""),
        }
    )
    for name in GATE_ROW_FIELDS:
        row[name] = None
    for kind in REPAIR_KINDS:
        row[f"repair_{kind}"] = None

    if out is not None:
        row["parse_success"] = out.parse_success
        if out.repairs is not None:
            row["repairs_changed"] = bool(out.repairs.get("changed"))
            row["repair_negative_cells"] = int(out.repairs.get("negative_cells", 0))
            row["repair_cells_changed"] = int(out.repairs.get("n_cells_changed", 0))
            row["repair_rows_changed"] = int(out.repairs.get("n_rows_changed", 0))
            for kind in REPAIR_KINDS:
                row[f"repair_{kind}"] = int(out.repairs.get(kind, 0))
        for key, value in (out.gate_row or {}).items():
            if key in row:
                row[key] = _jsonable(value)

    if scored is not None:
        for key, value in scored.items():
            if key in row:
                row[key] = _jsonable(value)

    return {name: row.get(name) for name in ROW_FIELDS}


# --------------------------------------------------------------------------- where output goes


def _is_inside(path: Path, root: Path) -> bool:
    """Whether ``path`` is ``root`` or lies under it."""
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def resolve_out_dir(
    out_dir: Optional[str],
    *,
    synthetic: bool,
    model_slug: str,
    stamp: str,
) -> Path:
    """Decide where a run writes, and refuse the destination that would mislead.

    There are two kinds of artefact and they must not share a directory:

    * a **real, paid run** on frozen ACN days produces the evidence behind a
      reported number, and belongs in the repository, under ``results/``;
    * a **smoke test** on synthetic fixture days produces numbers that were never
      measured, and must not land anywhere a reader could mistake for evidence.

    A synthetic run therefore refuses any destination inside the repository, with
    no flag to override it. The traces follow the output directory, so this one
    rule places every file the run writes.

    Args:
        out_dir: ``--out-dir``, or None for the default of this run's kind.
        synthetic: Whether the days are generated fixtures.
        model_slug: Filesystem-safe model id, for the default name.
        stamp: UTC timestamp, for the default name of a smoke run.

    Returns:
        The resolved directory. It is not created here.

    Raises:
        HarnessError: If a synthetic run points inside the repository.
    """
    if out_dir:
        path = Path(out_dir).expanduser().resolve()
    elif synthetic:
        # Path("") is Path("."), i.e. the working directory, which for this
        # project is inside the repository. Test the string, not the Path.
        configured = os.environ.get("EV_SMOKE_DIR", "").strip()
        root = (
            Path(configured).expanduser()
            if configured
            else Path(os.environ.get("TMPDIR", "/tmp")) / "ev-matrix-smoke"
        )
        path = (root / f"{stamp}_{model_slug}_SYNTHETIC").resolve()
    else:
        path = (PROJECT_ROOT / "results" / f"ev_matrix_{model_slug}").resolve()

    if synthetic and _is_inside(path, REPO_ROOT):
        raise HarnessError(
            "refusing to write a synthetic smoke test inside the repository.\n"
            f"  requested: {path}\n"
            f"  repository: {REPO_ROOT}\n"
            "The twenty benchmark days available today are generated fixtures, not measurements. "
            "Traces of a real, paid run are evidence and belong in the repository; traces of a "
            "smoke test do not. Pass --out-dir pointing outside the repository (or unset it and "
            "the run writes to $TMPDIR/ev-matrix-smoke/), or freeze the real ACN days first with "
            "scripts/freeze_benchmark_days.py."
        )
    if not synthetic and not _is_inside(path, REPO_ROOT):
        print(
            "WARNING: a real-data run is writing outside the repository, so its traces will not "
            f"be committed as evidence: {path}",
            file=sys.stderr,
        )
    return path


# --------------------------------------------------------------------------- pricing


def load_pricing(path: Optional[Path], model_key: str) -> Tuple[float, float, str]:
    """Input and output price per million tokens for a model, with its source.

    Args:
        path: Price book to read; defaults to the repository's shared one.
        model_key: Canonical ``provider:model`` id.

    Returns:
        ``(price_in, price_out, source)``. The prices are 0.0 when the model is
        in no book, which makes the dry run say so instead of printing a
        confident zero.
    """
    book: Dict[str, Any] = {}
    source = ""
    candidate = Path(path) if path else DEFAULT_PRICING_FILE
    if candidate.exists():
        try:
            book = json.loads(candidate.read_text(encoding="utf-8"))
            source = str(candidate)
        except (OSError, json.JSONDecodeError):
            book = {}
    entry = book.get(model_key)
    if entry is None:
        entry = FALLBACK_PRICING.get(model_key)
        source = f"{source or 'no price book'} + built-in fallback" if entry else source
    if entry is None:
        return 0.0, 0.0, f"no entry for {model_key} in {source or candidate}"
    return float(entry["input"]), float(entry["output"]), source or "built-in fallback"


# --------------------------------------------------------------------------- dry run

# Prompt tokens the EVAgent arm spends on material this harness cannot build
# offline: the parse system prompt, the agent system prompt, and the solver
# tool's JSON schema. Measured once from the trace of a single case14-sized run
# in the power-flow project and rounded up; the dry run prints it as an
# assumption so it can be argued with.
AGENT_FIXED_PROMPT_TOKENS = 500


def measure_prompt_tokens(arm: Arm, request: EVRequest) -> Tuple[int, str]:
    """Prompt tokens of one day-repeat of one arm, measured offline.

    No model is called and no key is read: the prompts are rebuilt with the same
    code the runner uses, which is the only estimate worth reading.

    Args:
        arm: The arm to measure.
        request: The request it would be given.

    Returns:
        ``(tokens_per_call, basis)``. Zero for an arm that calls no model.
    """
    if not arm.uses_llm:
        return 0, "no model call"
    if arm.strategy:
        messages = prompt_strategies.build_messages(arm.strategy, request)
        total = sum(estimate_tokens(m["content"]) for m in messages)
        return total, f"baseline/strategies.py::build_messages({arm.strategy!r})"
    from baseline.prompt import build_prompt_for_agent

    site, tou = build_site_tou(request)
    text = build_prompt_for_agent(request.day, site, tou, request.text)
    total = estimate_tokens(text) + estimate_tokens(request.text) + AGENT_FIXED_PROMPT_TOKENS
    return total, (
        "baseline/prompt.py::build_prompt_for_agent + the request text + "
        f"{AGENT_FIXED_PROMPT_TOKENS} tokens for the system prompts and the tool schema"
    )


def estimate_item_cost(arm: Arm, request: EVRequest, ledger: Ledger) -> float:
    """USD one day-repeat of one arm is expected to cost, for its reservation.

    The same numbers the dry run prints, for a single item: the prompt measured
    from the prompt the runner would really send, times the arm's own call
    count, plus its completion allowance. It is an estimate and it is meant to
    be one, because the ceiling has to be defended before the call is made and
    the real cost is only known after it. ``Reservation`` reconciles the two.

    Args:
        arm: The arm about to be launched.
        request: The request it will be given.
        ledger: The ledger whose prices the estimate is priced with.

    Returns:
        USD, or 0.0 for an arm that calls no model.
    """
    if not arm.uses_llm or arm.cost.n_calls <= 0:
        return 0.0
    prompt_per_call, _basis = measure_prompt_tokens(arm, request)
    calls = int(arm.cost.n_calls)
    prompt_tokens = int(round(calls * prompt_per_call * arm.cost.context_resend_factor))
    completion_tokens = calls * int(arm.cost.completion_tokens_per_call)
    return ledger.price(prompt_tokens, completion_tokens)


def estimate_run(
    arms: Sequence[Arm],
    requests: Sequence[EVRequest],
    *,
    repeats: int,
    price_in: float,
    price_out: float,
) -> List[Dict[str, Any]]:
    """Per-arm cost estimate of the whole matrix, without calling anything.

    Args:
        arms: The arms that would run.
        requests: The requests every arm would see, one per day per seed.
        repeats: Repeats per request.
        price_in, price_out: USD per million tokens.

    Returns:
        One dict per arm: items, calls, tokens, USD, and the basis of each
        number.
    """
    out: List[Dict[str, Any]] = []
    for arm in arms:
        items = len(requests) * int(repeats)
        prompt_per_call = 0
        basis = "no model call"
        if arm.uses_llm and requests:
            measured = [measure_prompt_tokens(arm, r) for r in requests]
            prompt_per_call = int(round(sum(m[0] for m in measured) / len(measured)))
            basis = measured[0][1]
        calls = items * arm.cost.n_calls
        prompt_tokens = int(round(calls * prompt_per_call * arm.cost.context_resend_factor))
        completion_tokens = calls * arm.cost.completion_tokens_per_call
        usd = prompt_tokens / 1e6 * price_in + completion_tokens / 1e6 * price_out
        out.append(
            {
                "arm": arm.name,
                "label": arm.label,
                "uses_llm": arm.uses_llm,
                "items": items,
                "calls_per_item": arm.cost.n_calls,
                "calls": calls,
                "prompt_tokens_per_call": prompt_per_call,
                "completion_tokens_per_call": arm.cost.completion_tokens_per_call,
                "context_resend_factor": arm.cost.context_resend_factor,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "usd": usd,
                "prompt_basis": basis,
                "cost_basis": arm.cost.basis,
            }
        )
    return out


def print_estimate(
    estimates: Sequence[Dict[str, Any]],
    *,
    model_key: str,
    price_in: float,
    price_out: float,
    price_source: str,
    budget_usd: float,
    synthetic: bool,
    out_dir: Path,
    n_days: int,
    seeds: Sequence[int],
    repeats: int,
) -> float:
    """Print the dry-run estimate and return the total USD.

    Nothing is called and nothing is written. This is the artefact the run is
    approved from, so it prints every assumption next to every number.
    """
    banner = SMOKE_BANNER if synthetic else REAL_BANNER
    print("=" * 78)
    print("DRY RUN - no model was called, nothing was written, nothing was spent")
    print("=" * 78)
    print(banner if synthetic else f"# {banner}")
    print()
    print(f"# model      : {model_key}")
    print(f"# price      : ${price_in}/M prompt, ${price_out}/M completion  ({price_source})")
    print(f"# days       : {n_days}   seeds: {list(seeds)}   repeats: {repeats}")
    print(f"# budget     : ${budget_usd:.2f} ceiling   (project credit at last check: ~$3.28)")
    print(f"# out dir    : {out_dir}")
    print(f"# tokeniser  : offline estimate at {CHARS_PER_TOKEN} characters per token")
    print()
    header = f"{'arm':<28} {'items':>6} {'calls':>7} {'prompt tok':>12} {'compl tok':>11} {'USD':>9}"
    print(header)
    print("-" * len(header))
    total = 0.0
    for row in estimates:
        total += float(row["usd"])
        print(
            f"{row['arm']:<28} {row['items']:>6} {row['calls']:>7} "
            f"{row['prompt_tokens']:>12,} {row['completion_tokens']:>11,} {row['usd']:>9.4f}"
        )
    print("-" * len(header))
    print(f"{'TOTAL':<28} {'':>6} {'':>7} {'':>12} {'':>11} {total:>9.4f}")
    print()
    print("# assumptions, per arm:")
    for row in estimates:
        if not row["uses_llm"]:
            print(f"#   {row['arm']}: no model call")
            continue
        print(
            f"#   {row['arm']}: {row['calls_per_item']} call(s) per day-repeat, "
            f"{row['prompt_tokens_per_call']:,} prompt tokens per call measured from "
            f"{row['prompt_basis']}, x{row['context_resend_factor']:g} for context re-send, "
            f"{row['completion_tokens_per_call']:,} completion tokens assumed"
        )
        if row["cost_basis"]:
            print(f"#       basis: {row['cost_basis']}")
    print()
    print(
        "# A provider bills the prompt it receives, not this estimate. Retries, a long "
        "chain-of-thought reply and a gate retry all push the real number up; budget 2-3x."
    )
    if total > budget_usd:
        print(
            f"# WARNING: the estimate ${total:.4f} is above the ceiling ${budget_usd:.2f}. "
            "The run would stop part-way and write over_budget rows.",
            file=sys.stderr,
        )
    return total


# --------------------------------------------------------------------------- aggregation


def _rate(values: Sequence[Any]) -> Dict[str, Any]:
    """``{"rate", "count", "total"}`` over booleans, ignoring None.

    Same shape as ``evaluation/metrics.py::rate``, so a column always arrives
    with the denominator it was computed over.
    """
    vals = [bool(v) for v in values if v is not None]
    total = len(vals)
    count = sum(1 for v in vals if v)
    return {"rate": (count / total) if total else None, "count": count, "total": total}


def _mean(values: Sequence[Any]) -> Optional[float]:
    """Mean of the numeric values, or None when there are none."""
    nums = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return (sum(nums) / len(nums)) if nums else None


def _session_rate(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Formulation over sessions: exact sessions over ground-truth sessions.

    This is the column Table S3 of the supplement defines, "the percentage of
    sessions where the parameters the LLM extracts from the request equal the
    structured session data". The day-level verdict is a different and much
    harsher quantity: a day counts as exact only when all of its sessions are,
    and with a median of 43 sessions per day it can print zero while almost
    every session was read correctly. Both are reported, this one as ``Form.``
    and the day verdict as ``Form. days``.

    Only rows whose arm exposes an extraction step contribute, which is the same
    filter the day-level rate uses. A row that was scored before the denominator
    was stored falls back to its ground-truth session count.

    Args:
        rows: The scored rows of one arm.

    Returns:
        ``{"rate", "count", "total"}``, where ``count`` is exact sessions and
        ``total`` is ground-truth sessions, as every other column carries its
        own denominator.
    """
    count = 0
    total = 0
    for row in rows:
        if row.get("formulation_status") not in ("pass", "fail"):
            continue
        exact = row.get("n_sessions_exact")
        if exact is None:
            continue
        truth = row.get("n_sessions_truth")
        if truth is None:
            truth = row.get("n_sessions")
        if truth is None:
            continue
        count += int(exact)
        total += int(truth)
    return {"rate": (count / total) if total else None, "count": count, "total": total}


def summarise(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One scoreboard entry per arm, every rate carrying its denominator.

    Rates are computed over the rows that were actually scored: a failed row
    counts in ``n_items`` and ``n_failed`` and in no rate, so a column can never
    be quietly improved by an arm that crashed on its hard days. ``n_failed`` is
    printed next to every rate for exactly that reason.

    Args:
        rows: Per-day rows as ``build_row`` produced them.

    Returns:
        One dict per arm, in the order the arms first appear.
    """
    order: List[str] = []
    by_arm: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        arm = str(row.get("arm"))
        if arm not in by_arm:
            by_arm[arm] = []
            order.append(arm)
        by_arm[arm].append(row)

    out: List[Dict[str, Any]] = []
    for arm in order:
        items = by_arm[arm]
        ok = [r for r in items if r.get("status") == "ok"]
        failed = [r for r in items if r.get("status") != "ok"]
        entry: Dict[str, Any] = {
            "arm": arm,
            "arm_label": items[0].get("arm_label"),
            "n_items": len(items),
            "n_ok": len(ok),
            "n_failed": len(failed),
            "failure_reasons": sorted({str(r.get("status")) for r in failed}),
            "solved": _rate([r.get("solved") for r in ok]),
            "escalated": _rate([r.get("escalated") for r in ok]),
            "wrong_unflagged": _rate([r.get("wrong_unflagged") for r in ok]),
            # Form. is per session, the definition the supplement states; the
            # per-day verdict is kept beside it rather than dropped.
            "formulation_exact": _session_rate(ok),
            "formulation_days": _rate(
                [r.get("formulation_status") == "pass" for r in ok if r.get("formulation_status") in ("pass", "fail")]
            ),
            "feasible": _rate([r.get("no_hard_violation") for r in ok]),
            "traceable": _rate(
                [r.get("traceability_status") == "pass" for r in ok if r.get("traceability_status") in ("pass", "fail")]
            ),
            "answer_correct": _rate(
                [r.get("answer_status") == "pass" for r in ok if r.get("answer_status") in ("pass", "fail")]
            ),
            "gap_pct_mean": _mean([r.get("gap_pct") for r in ok]),
            "cost_usd_mean": _mean([r.get("cost_usd") for r in ok]),
            "unmet_kwh_mean": _mean([r.get("unmet_kwh") for r in ok]),
            "pct_fully_served_mean": _mean([r.get("pct_fully_served") for r in ok]),
            "repairs_changed": _rate([r.get("repairs_changed") for r in ok]),
            "negative_cells_total": sum(int(r.get("repair_negative_cells") or 0) for r in ok),
            "repair_rows_total": sum(int(r.get("repair_rows_changed") or 0) for r in ok),
            "prompt_tokens": sum(int(r.get("prompt_tokens") or 0) for r in items),
            "completion_tokens": sum(int(r.get("completion_tokens") or 0) for r in items),
            "n_llm_calls": sum(int(r.get("n_llm_calls") or 0) for r in items),
            "n_tool_calls": sum(int(r.get("n_tool_calls") or 0) for r in items),
            "est_cost_usd": sum(float(r.get("est_cost_usd") or 0.0) for r in items),
            "wall_s": sum(float(r.get("wall_s") or 0.0) for r in items),
            "model_resolved": sorted({str(r.get("model_resolved") or "") for r in items if r.get("model_resolved")}),
            "prompt_hashes": sorted({str(r.get("system_prompt_hash") or "") for r in items if r.get("system_prompt_hash")}),
        }
        out.append(entry)
    return out


def _fmt_rate(entry: Optional[Dict[str, Any]]) -> str:
    """``62.5% (5/8)``, or ``n/a (0/0)`` when nothing was measured."""
    if not entry or entry.get("total") in (0, None):
        return "n/a (0/0)"
    return f"{100.0 * float(entry['rate']):.1f}% ({entry['count']}/{entry['total']})"


def _fmt_num(value: Optional[float], digits: int = 2) -> str:
    """A number with fixed digits, or ``--`` when there is none."""
    return "--" if value is None else f"{float(value):.{digits}f}"


SCOREBOARD_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("arm", "arm"),
    ("n", "items"),
    ("failed", "failed"),
    ("solved", "Solved"),
    ("escalated", "Escalated"),
    ("wrong_unflagged", "Wrong unflagged"),
    ("formulation_exact", "Form."),
    ("formulation_days", "Form. days"),
    ("feasible", "FR"),
    ("traceable", "Traceable"),
    ("answer_correct", "Answer"),
    ("gap_pct_mean", "gap %"),
    ("cost_usd_mean", "cost $"),
    ("repairs_changed", "repaired"),
    ("est_cost_usd", "USD"),
)


def scoreboard_markdown(summary: Sequence[Dict[str, Any]], meta: Dict[str, Any]) -> str:
    """The scoreboard as Markdown, with the smoke-test banner first when it applies."""
    lines: List[str] = []
    if meta.get("synthetic"):
        lines += [
            "> # SMOKE TEST - SYNTHETIC FIXTURE DAYS - DO NOT CITE",
            ">",
            f"> {SMOKE_BANNER}",
            "",
            "# EV Scheduling Benchmark Matrix [SMOKE TEST, SYNTHETIC DATA]",
        ]
    else:
        lines.append("# EV Scheduling Benchmark Matrix")
    lines += [
        "",
        f"model={meta.get('model_spec')} resolved={', '.join(meta.get('models_resolved') or []) or 'n/a'}  ",
        f"days={meta.get('n_days')} seeds={meta.get('seeds')} repeats={meta.get('repeats')} "
        f"items/arm={meta.get('items_per_arm')}  ",
        f"data_source={meta.get('data_source')} synthetic={meta.get('synthetic')} "
        f"requests_digest={meta.get('requests_digest')}  ",
        f"budget_ceiling_usd={meta.get('budget_usd')} spent_usd={_fmt_num(meta.get('spent_usd'), 4)} "
        f"traceability_policy={meta.get('traceability_policy')}  ",
        "",
        "| " + " | ".join(title for _, title in SCOREBOARD_COLUMNS) + " |",
        "|" + "|".join("---" for _ in SCOREBOARD_COLUMNS) + "|",
    ]
    for entry in summary:
        cells = [
            str(entry["arm"]),
            str(entry["n_items"]),
            str(entry["n_failed"]),
            _fmt_rate(entry["solved"]),
            _fmt_rate(entry["escalated"]),
            _fmt_rate(entry["wrong_unflagged"]),
            _fmt_rate(entry["formulation_exact"]),
            _fmt_rate(entry["formulation_days"]),
            _fmt_rate(entry["feasible"]),
            _fmt_rate(entry["traceable"]),
            _fmt_rate(entry["answer_correct"]),
            _fmt_num(entry["gap_pct_mean"]),
            _fmt_num(entry["cost_usd_mean"]),
            _fmt_rate(entry["repairs_changed"]),
            _fmt_num(entry["est_cost_usd"], 4),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "Every rate carries its denominator. `n/a (0/0)` means the term was not measured for that "
        "arm, which is not the same as passing: `Form.` needs an extraction step, `Traceable` "
        "needs a tool output for the numbers to trace to, and `Escalated` needs a gate.",
        "",
        "`Form.` is per session, over ground-truth sessions, which is what the supplement's "
        "Table S3 defines. `Form. days` is the day verdict: a day counts only when every one of "
        "its sessions is exact, so it is near zero on days with dozens of cars and is printed "
        "next to the per-session rate rather than in place of it.",
        "",
        "`Solved` is the conjunction of the state check, traceability, the answer check and the "
        "gate. Formulation is not one of its terms, so a wrong formulation is visible in `Form.` "
        "alone. It usually still costs the day its `Solved`, through the state check: a schedule "
        "optimised on misread parameters breaks the real session's constraint.",
        "",
        "`failed` counts rows the arm did not complete. They are written to the rows files with "
        "their error and are excluded from every rate above, so a rate must always be read next "
        "to it.",
    ]
    if meta.get("synthetic"):
        lines += ["", f"**{SMOKE_BANNER}**"]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- persistence


class RowAppender:
    """Appends each row to ``rows.jsonl`` the moment the item that made it ends.

    Until this existed nothing but the traces and ``requests.jsonl`` reached the
    disk before the run finished, so a two-hour run that was killed lost every
    scored row even though the expensive part, the traces, had survived. It also
    gives the live progress signal the power-flow study has and this one did not.

    The lines land in completion order, which under several workers is not the
    order of the matrix. That is a property of a partial file only: ``write_rows``
    rewrites the same path sorted at the end of the run, so the artefact a reader
    reads is the deterministic one whether the run was serial or parallel.

    Attributes:
        path: The file being appended to.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._handle = self.path.open("w", encoding="utf-8")

    def append(self, row: Dict[str, Any]) -> None:
        """Write one row and flush it, so a killed run keeps what it scored."""
        line = json.dumps(_jsonable(row), ensure_ascii=False)
        with self._lock:
            if self._handle.closed:
                return
            self._handle.write(line + "\n")
            self._handle.flush()

    def close(self) -> None:
        """Close the handle, so ``write_rows`` can rewrite the file in order."""
        with self._lock:
            if not self._handle.closed:
                self._handle.close()


def write_rows(out_dir: Path, rows: Sequence[Dict[str, Any]]) -> Tuple[Path, Path]:
    """Write the per-day rows as CSV and JSONL and return both paths.

    The CSV is the spreadsheet view and truncates the answer text; the JSONL is
    the complete record and truncates nothing, so a later question about a
    scoring definition can be answered from the committed rows without paying
    for the matrix again.

    This rewrites the ``rows.jsonl`` that ``RowAppender`` has been appending to,
    in the run's own order rather than in the order the items happened to
    finish. Both files therefore look the same for a given matrix however many
    workers ran it.
    """
    csv_path = out_dir / "rows.csv"
    jsonl_path = out_dir / "rows.jsonl"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ROW_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            text = flat.get("answer_text") or ""
            if len(str(text)) > CSV_TEXT_CHARS:
                flat["answer_text"] = str(text)[:CSV_TEXT_CHARS] + " ...[truncated, see rows.jsonl]"
            for key, value in list(flat.items()):
                if isinstance(value, (list, dict)):
                    flat[key] = json.dumps(_jsonable(value), ensure_ascii=False)
            writer.writerow(flat)
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_jsonable(row), ensure_ascii=False) + "\n")
    return csv_path, jsonl_path


def write_scoreboard(
    out_dir: Path, summary: Sequence[Dict[str, Any]], meta: Dict[str, Any]
) -> Tuple[Path, Path, Path]:
    """Write ``scoreboard.md``, ``scoreboard.csv`` and ``scoreboard.json``."""
    md_path = out_dir / "scoreboard.md"
    csv_path = out_dir / "scoreboard.csv"
    json_path = out_dir / "scoreboard.json"
    md_path.write_text(scoreboard_markdown(summary, meta), encoding="utf-8")

    flat_fields = [
        "arm", "arm_label", "smoke_test_synthetic_data", "n_items", "n_ok", "n_failed",
        "solved_rate", "solved_count", "solved_total",
        "escalated_rate", "escalated_count", "escalated_total",
        "wrong_unflagged_rate", "wrong_unflagged_count", "wrong_unflagged_total",
        "formulation_rate", "formulation_count", "formulation_total",
        "formulation_days_rate", "formulation_days_count", "formulation_days_total",
        "feasible_rate", "feasible_count", "feasible_total",
        "traceable_rate", "traceable_count", "traceable_total",
        "answer_rate", "answer_count", "answer_total",
        "gap_pct_mean", "cost_usd_mean", "unmet_kwh_mean", "pct_fully_served_mean",
        "repairs_changed_rate", "repairs_changed_count", "repairs_changed_total",
        "negative_cells_total", "repair_rows_total",
        "prompt_tokens", "completion_tokens", "n_llm_calls", "n_tool_calls",
        "est_cost_usd", "wall_s",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=flat_fields, extrasaction="ignore")
        writer.writeheader()
        for entry in summary:
            flat = {
                "arm": entry["arm"],
                "arm_label": entry["arm_label"],
                "smoke_test_synthetic_data": bool(meta.get("synthetic")),
                "n_items": entry["n_items"],
                "n_ok": entry["n_ok"],
                "n_failed": entry["n_failed"],
                "gap_pct_mean": entry["gap_pct_mean"],
                "cost_usd_mean": entry["cost_usd_mean"],
                "unmet_kwh_mean": entry["unmet_kwh_mean"],
                "pct_fully_served_mean": entry["pct_fully_served_mean"],
                "negative_cells_total": entry["negative_cells_total"],
                "repair_rows_total": entry["repair_rows_total"],
                "prompt_tokens": entry["prompt_tokens"],
                "completion_tokens": entry["completion_tokens"],
                "n_llm_calls": entry["n_llm_calls"],
                "n_tool_calls": entry["n_tool_calls"],
                "est_cost_usd": entry["est_cost_usd"],
                "wall_s": entry["wall_s"],
            }
            for key, prefix in (
                ("solved", "solved"), ("escalated", "escalated"),
                ("wrong_unflagged", "wrong_unflagged"), ("formulation_exact", "formulation"),
                ("formulation_days", "formulation_days"),
                ("feasible", "feasible"), ("traceable", "traceable"),
                ("answer_correct", "answer"), ("repairs_changed", "repairs_changed"),
            ):
                part = entry[key]
                flat[f"{prefix}_rate"] = part["rate"]
                flat[f"{prefix}_count"] = part["count"]
                flat[f"{prefix}_total"] = part["total"]
            writer.writerow(flat)

    json_path.write_text(
        json.dumps({"meta": _jsonable(meta), "arms": _jsonable(list(summary))}, indent=2),
        encoding="utf-8",
    )
    return md_path, csv_path, json_path


def write_manifest(out_dir: Path, meta: Dict[str, Any]) -> Path:
    """Write ``run_manifest.json``: the whole protocol of this run, in one file."""
    path = out_dir / "run_manifest.json"
    path.write_text(json.dumps(_jsonable(meta), indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_smoke_sentinel(out_dir: Path, meta: Dict[str, Any]) -> Path:
    """Write the sentinel file that marks a directory as a smoke test."""
    path = out_dir / SMOKE_SENTINEL_NAME
    path.write_text(
        "\n".join(
            [
                "SMOKE TEST - SYNTHETIC FIXTURE DAYS - DO NOT CITE",
                "",
                SMOKE_BANNER,
                "",
                f"run_id      : {meta.get('run_id')}",
                f"created_at  : {meta.get('created_at')}",
                f"model       : {meta.get('model_spec')}",
                f"days        : {meta.get('n_days')}  seeds: {meta.get('seeds')}",
                f"data_source : {meta.get('data_source')}",
                "",
                store.SYNTHETIC_WARNING,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------- preflight


def preflight(arms: Sequence[Arm], spec: ModelSpec, *, client: Optional[Any] = None) -> None:
    """Refuse to start when an arm that was asked for cannot run.

    This is the rule ``scripts/run_agent_vs_baseline.py`` gets wrong. That script
    returns None from both LLM phases when ``OPENAI_API_KEY`` is absent, which
    with OpenRouter-only credentials produces a results table with no LLM in it
    and no sign that anything is missing. Nothing here is skipped: an arm that
    cannot run stops the run.

    Args:
        arms: The arms about to run.
        spec: The resolved model spec.
        client: A pre-built client (a stub, in tests). When given, no key is
            needed and none is read.

    Raises:
        HarnessError: If an LLM arm was requested and no key resolves for the
            provider, or the ``openai`` package is missing.
    """
    llm_arms = [a.name for a in arms if a.uses_llm]
    if not llm_arms or client is not None:
        return
    if not resolve_api_key(spec.provider):
        raise HarnessError(
            f"{missing_key_message(spec)}\n"
            f"  arms that need it: {', '.join(llm_arms)}\n"
            "  Refusing to run: dropping an LLM arm silently is how a results table ends up "
            "with no LLM in it and still looks normal."
        )
    try:
        import openai  # noqa: F401
    except ImportError as exc:
        raise HarnessError(
            "the 'openai' package is not installed, and every LLM arm needs it "
            f"({', '.join(llm_arms)}). Install it with 'pip install openai>=1.0.0'."
        ) from exc


# --------------------------------------------------------------------------- the matrix


def load_requests(
    *,
    seeds: Sequence[int],
    dates: Optional[Sequence[_date]],
    site_id: str,
    source: str,
) -> List[Tuple[int, EVRequest]]:
    """The request list every arm will share, as ``(seed, request)`` pairs.

    Generated once, before any arm runs, and handed to all of them. That is what
    "same days, same requests, same seed" means operationally: not that each arm
    regenerates the same thing, but that there is one list and every arm is
    given it.
    """
    out: List[Tuple[int, EVRequest]] = []
    for seed in seeds:
        for request in load_benchmark_requests(
            seed=int(seed), site_id=site_id, dates=dates, source=source
        ):
            out.append((int(seed), request))
    return out


def requests_digest(pairs: Sequence[Tuple[int, EVRequest]]) -> str:
    """Digest of the shared request list: ids, seeds and the exact texts.

    Stored on every row and in the manifest. Two arms whose rows carry the same
    digest were given the same inputs, and that can be checked after the fact
    rather than asserted in prose.
    """
    return sha256_json(
        [[seed, r.id, r.variant, sha256_text(r.text)] for seed, r in pairs]
    )


@dataclass(frozen=True)
class _Item:
    """One unit of work: one arm, on one day, at one seed, on one repeat.

    Attributes:
        index: Position in the run's order, which is the order every artefact
            is written in.
        arm: The arm to run.
        seed: The request-generation seed of ``request``.
        request: The request every arm is given for this day.
        repeat: Which repeat of that request this is.
        item_id: Day, seed and repeat, as it appears in a trace file name.
    """

    index: int
    arm: Arm
    seed: int
    request: EVRequest
    repeat: int
    item_id: str


def plan_items(
    arms: Sequence[Arm], pairs: Sequence[Tuple[int, EVRequest]], repeats: int
) -> List[_Item]:
    """Every item of the matrix, in the one order its artefacts are written in.

    Sorted by arm, then date, then seed, then repeat, with the arms kept in the
    order they were asked for. The order is a property of the matrix and not of
    the scheduler, which is what lets ``--workers`` exist at all: rows.csv,
    rows.jsonl, the scoreboard and the manifest of a run with eight workers are
    the same bytes as those of a serial run over the same inputs, and a reader
    cannot tell from the artefacts which one produced them.

    Args:
        arms: The arms to run, already resolved.
        pairs: ``(seed, request)`` pairs shared by every arm.
        repeats: Repeats per request.

    Returns:
        The items, ordered and indexed.
    """
    ordered: List[Tuple[int, str, int, int, Arm, EVRequest]] = []
    for position, arm in enumerate(arms):
        for seed, request in pairs:
            for repeat in range(int(repeats)):
                ordered.append(
                    (position, str(request.date or ""), int(seed), int(repeat), arm, request)
                )
    ordered.sort(key=lambda entry: (entry[0], entry[1], entry[2], entry[3]))
    items: List[_Item] = []
    for index, (_position, _date, seed, repeat, arm, request) in enumerate(ordered):
        items.append(
            _Item(
                index=index,
                arm=arm,
                seed=seed,
                request=request,
                repeat=repeat,
                item_id=f"{request.date or request.id}_s{seed}_r{repeat}",
            )
        )
    return items


def run_matrix(
    *,
    arms: Sequence[Arm],
    pairs: Sequence[Tuple[int, EVRequest]],
    spec: ModelSpec,
    model_requested: str,
    out_dir: Path,
    run_id: str,
    repeats: int,
    max_tool_rounds: int,
    max_completion_tokens: int,
    traceability_policy: str,
    ledger: Ledger,
    synthetic: bool,
    data_source: str,
    inner_client: Optional[Any] = None,
    write_trace: bool = True,
    progress: bool = True,
    workers: int = DEFAULT_WORKERS,
) -> List[Dict[str, Any]]:
    """Run every arm over every request and return the per-day rows.

    The items are planned first, by ``plan_items``, and the rows come back in
    that order whether they were run one at a time or ``workers`` at a time. Each
    row is also appended to ``rows.jsonl`` as soon as it is scored, so a run that
    is killed keeps everything it had already scored rather than only its traces.

    Concurrency is opt-in and applies within the matrix, which keeps whole arms
    together in the output and spreads the I/O-bound model calls over threads.
    Three things hold at any number of workers. The budget is defended by a
    reservation taken before an item is launched, so ``N`` calls in flight cannot
    pass the ceiling by ``N`` items' worth of spend; every artefact is written in
    the planned order; and an item that raises becomes a failed row without
    taking the pool or the items beside it down with it.

    Args:
        arms: The arms to run, already resolved.
        pairs: ``(seed, request)`` pairs shared by every arm.
        spec: Resolved model spec.
        model_requested: The model id as the user wrote it.
        out_dir: Where the run writes; traces go to ``out_dir/traces`` and the
            rows are appended to ``out_dir/rows.jsonl`` as they complete.
        run_id: Identifier of this run.
        repeats: Repeats per request.
        max_tool_rounds: Tool rounds allowed to the agent arm.
        max_completion_tokens: Completion cap applied to every LLM arm.
        traceability_policy: One of ``TRACEABILITY_POLICIES``.
        ledger: Budget accounting, shared across arms and across workers.
        synthetic: Whether the days are fixtures.
        data_source: The loader source used.
        inner_client: A pre-built client; a stub in tests.
        write_trace: Set False to skip writing component traces.
        progress: Print one line per item, as it finishes.
        workers: Items in flight at once. 1 is the serial path.

    Returns:
        The rows, in the order ``plan_items`` put the items in.
    """
    digest = requests_digest(pairs)
    trace_root = out_dir / "traces"
    items = plan_items(arms, pairs, repeats)
    n_workers = max(1, int(workers))
    rows: List[Optional[Dict[str, Any]]] = [None] * len(items)
    halted = threading.Event()
    print_lock = threading.Lock()

    out_dir.mkdir(parents=True, exist_ok=True)
    appender = RowAppender(out_dir / "rows.jsonl")

    def _context(item: _Item, reservation: Optional[Reservation]) -> RunContext:
        """The context one item runs in; identical for every arm but the arm."""
        client = (
            RecordingClient(
                inner_client,
                max_completion_tokens=max_completion_tokens,
                ledger=ledger,
                reservation=reservation,
            )
            if (item.arm.uses_llm and inner_client is not None)
            else None
        )
        return RunContext(
            arm=item.arm,
            request=item.request,
            seed=item.seed,
            repeat=item.repeat,
            spec=spec,
            model_requested=model_requested,
            trace_dir=trace_root / item.arm.name.replace(":", "_"),
            run_id=item.item_id,
            max_tool_rounds=max_tool_rounds,
            max_completion_tokens=max_completion_tokens,
            client=client,
            write_trace=write_trace,
        )

    def _row(ctx: RunContext, out, scored, **kwargs: Any) -> Dict[str, Any]:
        """``build_row`` with the fields every row of this run shares."""
        return build_row(
            ctx, out, scored,
            requests_digest=digest, synthetic=synthetic, data_source=data_source,
            traceability_policy=traceability_policy, **kwargs,
        )

    def _record(item: _Item, row: Dict[str, Any]) -> None:
        """Keep a finished row in its place, append it, and report it."""
        rows[item.index] = row
        appender.append(row)
        if progress:
            with print_lock:
                print(
                    f"  {item.arm.name:<26} {item.item_id:<22} {row['status']:<11} "
                    f"{str(row.get('outcome') or '-'):<16} ${ledger.spent_usd:.4f}"
                )

    def _run_item(item: _Item, ctx: RunContext, reservation: Reservation) -> Dict[str, Any]:
        """Run one item and return its row, whatever it does.

        Nothing may propagate out of here. A worker that raises would take the
        items beside it with it, and a failed item has to come back as a row
        with its error, exactly as it does on the serial path.
        """
        runner = RUNNERS[item.arm.name]
        try:
            try:
                out = runner(ctx)
                scored = score_row(ctx, out, traceability_policy=traceability_policy)
                return _row(ctx, out, scored, status="ok",
                            est_cost_usd=float(reservation.actual_usd))
            except BudgetExceeded as exc:
                halted.set()
                with print_lock:
                    print(f"BUDGET: {exc}", file=sys.stderr)
                return _row(ctx, None, None, status="over_budget", error=str(exc),
                            est_cost_usd=float(reservation.actual_usd))
            except Exception as exc:  # noqa: BLE001 - a failed row is the point
                with print_lock:
                    print(
                        f"FAILED {item.arm.name} {item.item_id}: {type(exc).__name__}: {exc}",
                        file=sys.stderr,
                    )
                    if os.environ.get("EV_MATRIX_TRACEBACK"):
                        traceback.print_exc()
                return _row(ctx, None, None, status="failed",
                            error=f"{type(exc).__name__}: {exc}",
                            est_cost_usd=float(reservation.actual_usd))
        finally:
            ledger.release(reservation)

    next_index = 0
    pending: Dict[Future, Tuple[_Item, RunContext]] = {}
    try:
        with ThreadPoolExecutor(max_workers=n_workers, thread_name_prefix="ev_matrix") as pool:
            while next_index < len(items) or pending:
                while not halted.is_set() and next_index < len(items) and len(pending) < n_workers:
                    item = items[next_index]
                    try:
                        reservation = ledger.reserve(
                            f"{item.arm.name} {item.item_id}",
                            estimate_item_cost(item.arm, item.request, ledger),
                        )
                    except BudgetExceeded as exc:
                        halted.set()
                        with print_lock:
                            print(f"BUDGET: {exc}", file=sys.stderr)
                        _record(item, _row(_context(item, None), None, None,
                                           status="over_budget", error=str(exc)))
                        next_index += 1
                        break
                    ctx = _context(item, reservation)
                    next_index += 1
                    pending[pool.submit(_run_item, item, ctx, reservation)] = (item, ctx)
                if halted.is_set():
                    while next_index < len(items):
                        item = items[next_index]
                        _record(item, _row(
                            _context(item, None), None, None, status="over_budget",
                            error="not run: the budget ceiling was reached earlier in this run",
                        ))
                        next_index += 1
                if not pending:
                    continue
                done, _not_done = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    item, ctx = pending.pop(future)
                    try:
                        row = future.result()
                    except Exception as exc:  # noqa: BLE001 - the row is still owed
                        row = _row(ctx, None, None, status="failed",
                                   error=f"{type(exc).__name__}: {exc}")
                    _record(item, row)
    finally:
        appender.close()

    return [row for row in rows if row is not None]


# --------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    """Command-line interface of the harness."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.run_ev_matrix",
        description=(
            "Run every arm of the EV results table over every benchmark day, with identical "
            "days, requests, seeds and budget, and write the rows, scoreboard and traces a "
            "paper table is built from."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Registered arms: " + ", ".join(sorted(ARMS)) + "\n"
            "Nothing is ever skipped: an arm that cannot run stops the run, and a day that "
            "fails is written as a row with its error."
        ),
    )
    parser.add_argument(
        "--arm", action="append", dest="arms", metavar="NAME",
        help=f"Arm to run; repeatable. Default: {' '.join(DEFAULT_ARMS)}",
    )
    parser.add_argument("--model", default=os.environ.get("EV_LLM_MODEL", DEFAULT_MODEL),
                        help=f"Model id as provider:model (default {DEFAULT_MODEL}).")
    parser.add_argument("--site", default=store.BENCHMARK_SITE_ID, help="ACN site id.")
    parser.add_argument("--days", type=int, default=None,
                        help="Use only the first N benchmark days.")
    parser.add_argument("--date", action="append", dest="dates", metavar="YYYY-MM-DD",
                        help="Explicit day; repeatable. Overrides --days.")
    parser.add_argument("--seeds", type=int, nargs="+", default=[DEFAULT_SEED],
                        help="Request-generation seeds; every arm sees every seed.")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS,
                        help="Repeats per request, for run-to-run variance.")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=(
                            f"Items run at once (default {DEFAULT_WORKERS}, serial). The model "
                            "calls are I/O-bound, so a small pool cuts the wall time roughly in "
                            "proportion. The artefacts are identical either way."
                        ))
    parser.add_argument("--data-source", default="fixture", choices=("fixture", "cache", "auto", "api"),
                        help="Where the days come from. 'fixture' is the synthetic smoke set.")
    parser.add_argument("--out-dir", default=None,
                        help="Output directory. A synthetic run refuses a path inside the repository.")
    parser.add_argument("--budget-usd", type=float, default=DEFAULT_BUDGET_USD,
                        help=f"Spend ceiling (default {DEFAULT_BUDGET_USD}). The run stops at it.")
    parser.add_argument("--max-completion-tokens", type=int, default=MAX_COMPLETION_TOKENS,
                        help="Completion cap applied identically to every LLM arm.")
    parser.add_argument("--max-tool-rounds", type=int, default=DEFAULT_MAX_TOOL_ROUNDS,
                        help="Tool rounds allowed to the solver-grounded arm.")
    parser.add_argument("--traceability-policy", default="grounded_only", choices=TRACEABILITY_POLICIES,
                        help="Which arms the traceability term is measured for.")
    parser.add_argument("--pricing-file", default=None,
                        help=f"Price book (default {DEFAULT_PRICING_FILE}).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Estimate the cost per arm and in total, call nothing, write nothing.")
    parser.add_argument("--no-trace", action="store_true",
                        help="Do not write component traces (for a quick structural check).")
    parser.add_argument("--quiet", action="store_true", help="No per-item progress lines.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point. Returns 0 only when every row of every arm completed."""
    args = build_parser().parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    try:
        arms = resolve_arms(args.arms)
        if int(args.workers) < 1:
            raise HarnessError(f"--workers must be at least 1, got {args.workers}")
        spec = parse_model_spec(args.model)
        dates: Optional[List[_date]] = None
        if args.dates:
            dates = [_date.fromisoformat(d) for d in args.dates]
        elif args.days is not None:
            dates = list(store.BENCHMARK_DATES)[: int(args.days)]

        pairs = load_requests(
            seeds=args.seeds, dates=dates, site_id=args.site, source=args.data_source
        )
        if not pairs:
            raise HarnessError("no benchmark days selected; nothing to run")
        synthetic = args.data_source == "fixture" or any(r.synthetic for _s, r in pairs)
        out_dir = resolve_out_dir(
            args.out_dir, synthetic=synthetic, model_slug=spec.slug, stamp=stamp
        )
        price_in, price_out, price_source = load_pricing(
            Path(args.pricing_file) if args.pricing_file else None, spec.key
        )
        unique_days = sorted({r.date for _s, r in pairs})

        if args.dry_run:
            estimates = estimate_run(
                arms,
                [r for _s, r in pairs],
                repeats=args.repeats,
                price_in=price_in,
                price_out=price_out,
            )
            print_estimate(
                estimates,
                model_key=spec.key,
                price_in=price_in,
                price_out=price_out,
                price_source=price_source,
                budget_usd=args.budget_usd,
                synthetic=synthetic,
                out_dir=out_dir,
                n_days=len(unique_days),
                seeds=args.seeds,
                repeats=args.repeats,
            )
            return 0

        preflight(arms, spec)
        inner_client = build_client(spec) if any(a.uses_llm for a in arms) else None
        ledger = Ledger(price_in=price_in, price_out=price_out, limit_usd=float(args.budget_usd))
        run_id = f"ev_matrix_{stamp}_{spec.slug}" + ("_SYNTHETIC_SMOKE" if synthetic else "")

        out_dir.mkdir(parents=True, exist_ok=True)
        meta: Dict[str, Any] = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "case_study": "ev_scheduling",
            "harness": "scripts/run_ev_matrix.py",
            "synthetic": synthetic,
            "smoke_test": synthetic,
            "banner": SMOKE_BANNER if synthetic else REAL_BANNER,
            "data_source": args.data_source,
            "site_id": args.site,
            "dates": unique_days,
            "n_days": len(unique_days),
            "seeds": list(args.seeds),
            "repeats": args.repeats,
            "items_per_arm": len(pairs) * int(args.repeats),
            "arms": [a.name for a in arms],
            "arm_descriptions": {a.name: a.description for a in arms},
            "pending_arms": {
                name: arm.pending_reason for name, arm in ARMS.items() if not arm.implemented
            },
            "model_requested": args.model,
            "model_spec": spec.key,
            "max_completion_tokens": args.max_completion_tokens,
            "max_tool_rounds": args.max_tool_rounds,
            "traceability_policy": args.traceability_policy,
            "gap_tol_pct": GAP_TOL_PCT,
            # What the two moving columns meant on this run, so the directory
            # says it rather than the reader having to date the code.
            "solved_terms": list(SOLVED_TERMS),
            "formulation_aggregation": FORMULATION_AGGREGATION,
            "budget_usd": args.budget_usd,
            "price_in_per_mtok": price_in,
            "price_out_per_mtok": price_out,
            "price_source": price_source,
            "requests_digest": requests_digest(pairs),
            "strategies": {
                a.name: {
                    "strategy": a.strategy,
                    "sections": list(prompt_strategies.prompt_sections(a.strategy)),
                }
                for a in arms
                if a.strategy
            },
            "python": platform.python_version(),
            "out_dir": str(out_dir),
        }

        if synthetic:
            print("=" * 78, file=sys.stderr)
            print("SMOKE TEST - SYNTHETIC FIXTURE DAYS - DO NOT CITE", file=sys.stderr)
            print(SMOKE_BANNER, file=sys.stderr)
            print("=" * 78, file=sys.stderr)
            write_smoke_sentinel(out_dir, meta)

        to_jsonl([r for _s, r in pairs], out_dir / "requests.jsonl")
        print(f"# run_id {run_id}")
        print(f"# out    {out_dir}")
        print(f"# arms   {', '.join(a.name for a in arms)}")
        print(f"# items  {meta['items_per_arm']} per arm over {len(unique_days)} day(s)")
        print()

        rows = run_matrix(
            arms=arms,
            pairs=pairs,
            spec=spec,
            model_requested=args.model,
            out_dir=out_dir,
            run_id=run_id,
            repeats=args.repeats,
            max_tool_rounds=args.max_tool_rounds,
            max_completion_tokens=args.max_completion_tokens,
            traceability_policy=args.traceability_policy,
            ledger=ledger,
            synthetic=synthetic,
            data_source=args.data_source,
            inner_client=inner_client,
            write_trace=not args.no_trace,
            progress=not args.quiet,
            workers=int(args.workers),
        )

        summary = summarise(rows)
        meta["spent_usd"] = round(ledger.spent_usd, 6)
        meta["prompt_tokens"] = ledger.prompt_tokens
        meta["completion_tokens"] = ledger.completion_tokens
        meta["n_llm_calls"] = ledger.n_calls
        # Only rows that actually called a model; a placeholder from a rule arm in
        # this list would read as the alias having moved mid-run.
        meta["models_resolved"] = sorted(
            {
                str(r.get("model_resolved"))
                for r in rows
                if r.get("model_resolved") and ARMS[str(r.get("arm"))].uses_llm
            }
        )
        meta["n_failed"] = sum(1 for r in rows if r.get("status") != "ok")
        write_rows(out_dir, rows)
        write_scoreboard(out_dir, summary, meta)
        write_manifest(out_dir, meta)

        print()
        print(scoreboard_markdown(summary, meta))
        print(f"# wrote {out_dir}")
        print(
            "# next: "
            f"python -m scripts.ev_report {out_dir}"
        )
        if meta["n_failed"]:
            print(
                f"# {meta['n_failed']} row(s) did not complete; they are in rows.csv with their "
                "error and are excluded from every rate.",
                file=sys.stderr,
            )
            return 1
        return 0

    except HarnessError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
