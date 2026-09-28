"""The benchmark harness: fairness, loud failure, and where the artefacts land.

Offline and adversarial. Every model call is served by a stub client that is
constructed in the test, so no API key is read, no request is made, and nothing
is spent. The fixture days come from ``data/benchmark/fixtures/`` and the only
real computation is CVXPY.

Six things are pinned, and each of them is a defect this harness exists to
prevent rather than a feature it happens to have:

* **an arm is never dropped.** ``scripts/run_agent_vs_baseline.py`` returns None
  from both of its LLM phases when ``OPENAI_API_KEY`` is absent, which with
  OpenRouter-only credentials writes a results table with no LLM in it and no
  sign of it. ``preflight`` must raise instead, and an arm that fails mid-run
  must appear as a failed row with a non-zero exit;
* **a synthetic run cannot write inside the repository.** The twenty benchmark
  days are generated fixtures, so a clean-looking table from them is the most
  misleading artefact this project could produce. The refusal is tested from
  both sides: the in-repo path raises, and the default path is outside;
* **every arm gets the same inputs**, which is checked on the rows themselves
  through the request digest rather than asserted in prose;
* **both answers are on every row**, including the days whose request only
  prescribes an operation. The power-flow study discarded that value and then
  could not size a scoring defect without re-running;
* **the dry run calls nothing**, which is checked by giving it a client that
  fails the test if it is ever used;
* **``--workers`` buys wall time and nothing else.** The artefacts of a parallel
  run are compared byte for byte with a serial one, the ceiling is tested with
  several items in flight and none of them finished, and an item that raises is
  shown not to take the items beside it with it.
"""

import contextlib
import json
import threading
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pytest

from data.benchmark import store
from evaluation.requests import VARIANTS, build_request, extract_answer, load_benchmark_requests
from evaluation import report as ev_report
from evaluation import runner as matrix

SUBSET_DATES = [date(2019, 4, 15), date(2018, 12, 3)]

MODEL = "openrouter:openai/gpt-4o"


# --------------------------------------------------------------------------- stub client


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
    def __init__(self, content: Optional[str] = None, tool_calls: Optional[List[_FakeToolCall]] = None) -> None:
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none: bool = False) -> Dict[str, Any]:
        out: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            out["tool_calls"] = [tc.model_dump() for tc in self.tool_calls]
        return out


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message
        self.finish_reason = "stop"


class _FakeUsage:
    def __init__(self, prompt: int, completion: int) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = prompt + completion


class _FakeResponse:
    """A response that carries a resolved model id, as a real provider's does."""

    def __init__(self, message: _FakeMessage, *, model: str, prompt: int = 900, completion: int = 300) -> None:
        self.choices = [_FakeChoice(message)]
        self.usage = _FakeUsage(prompt, completion)
        self.model = model
        self.id = "stub-response"


class _Completions:
    def __init__(self, owner: "StubClient") -> None:
        self._owner = owner

    def create(self, **kwargs: Any) -> Any:
        return self._owner.respond(**kwargs)


class _Chat:
    def __init__(self, owner: "StubClient") -> None:
        self.completions = _Completions(owner)


class StubClient:
    """A client that answers each arm plausibly, and records what it was sent.

    It dispatches on the payload rather than on a fixed script, because the arms
    call it in different shapes: the no-tools arm sends one message pair, the
    parse step asks for JSON, the planner asks for a JSON plan, and the agent
    loop offers tools and then asks for an explanation.

    Attributes:
        resolved_model: The id the stub reports back, standing in for the
            identifier a provider returns when a moving alias is requested.
        payloads: Every ``create`` kwargs dict, in order.
    """

    def __init__(
        self,
        *,
        resolved_model: str = "openai/gpt-4o-2024-11-20",
        reply_text: str = "",
        prompt_tokens: int = 900,
        completion_tokens: int = 300,
    ) -> None:
        self.resolved_model = resolved_model
        self.reply_text = reply_text
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.payloads: List[Dict[str, Any]] = []
        self.chat = _Chat(self)

    # -- the three shapes -------------------------------------------------

    def respond(self, **kwargs: Any) -> Any:
        self.payloads.append(kwargs)
        messages = kwargs.get("messages") or []
        text = "\n".join(str(m.get("content") or "") for m in messages)
        has_tools = bool(kwargs.get("tools"))
        has_tool_result = any(m.get("role") == "tool" for m in messages)

        if '{"plan":' in text and not has_tools:
            # the planner's turn: one solver call, planned before any result exists
            message = _FakeMessage(content='{"plan": [{"tool": "solve_ev_schedule", "args": {}}]}')
        elif "JSON" in text and "sessions" in text and not has_tools:
            message = _FakeMessage(content=self._parse_json(text))
        elif has_tools and not has_tool_result:
            message = _FakeMessage(
                content=None,
                tool_calls=[_FakeToolCall("call-1", "solve_ev_schedule", "{}")],
            )
        elif has_tool_result:
            message = _FakeMessage(content=self._explanation(messages))
        else:
            message = _FakeMessage(content=self.reply_text or "Answer: 1.00 kWh")
        return _FakeResponse(
            message,
            model=self.resolved_model,
            prompt=self.prompt_tokens,
            completion=self.completion_tokens,
        )

    def _parse_json(self, text: str) -> str:
        """A parse reply that reproduces the day the request text describes."""
        sessions = []
        for session in (self.day.sessions if self.day is not None else []):
            sessions.append(
                {
                    "arrival_hour": session.arrival_idx * 0.25,
                    "departure_hour": session.departure_idx * 0.25,
                    "energy_kwh": session.energy_kwh,
                    "max_power_kw": session.max_power_kw,
                }
            )
        return json.dumps({"sessions": sessions, "n_steps": 96, "dt_hours": 0.25})

    def _explanation(self, messages: List[Dict[str, Any]]) -> str:
        """An explanation that quotes the tool's own numbers, so E3/E4 can pass."""
        for message in reversed(messages):
            if message.get("role") == "tool":
                try:
                    payload = json.loads(message.get("content") or "{}")
                except json.JSONDecodeError:
                    payload = {}
                cost = payload.get("total_cost_usd")
                unmet = payload.get("total_unmet_kwh")
                return (
                    f"The schedule costs ${cost} and leaves {unmet} kWh undelivered. "
                    f"Answer: ${cost}"
                )
        return "Answer: 0"

    day: Any = None


class ExplodingClient:
    """A client that fails the test if anything calls it."""

    def __init__(self) -> None:
        self.chat = _Chat(self)

    def respond(self, **kwargs: Any) -> Any:
        raise AssertionError("a model call was made when none was allowed")


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def requests_two_days():
    """Two small fixture days, as ``(seed, EVRequest)`` pairs."""
    return matrix.load_requests(seeds=[0], dates=SUBSET_DATES, site_id="caltech", source="fixture")


def _ctx(arm_name: str, request, tmp_path: Path, client=None) -> matrix.RunContext:
    return matrix.RunContext(
        arm=matrix.ARMS[arm_name],
        request=request,
        seed=0,
        repeat=0,
        spec=matrix.parse_model_spec(MODEL),
        model_requested=MODEL,
        trace_dir=tmp_path / "traces",
        run_id="test",
        client=client,
        write_trace=False,
    )


# --------------------------------------------------------------------------- the registry


def test_default_arms_are_all_runnable():
    """Every default arm is implemented and has a runner."""
    arms = matrix.resolve_arms(None)
    assert [a.name for a in arms] == list(matrix.DEFAULT_ARMS)
    for arm in arms:
        assert arm.implemented
        assert arm.name in matrix.RUNNERS


def test_a_pending_arm_would_refuse_rather_than_vanish():
    """A registered arm that is not implemented is an error with a reason, never a missing row."""
    arm = matrix.Arm(name="ghost", label="Ghost", uses_llm=True, has_gate=False, scores_formulation=False,
                     grounded=False, implemented=False, pending_reason="a scope decision is open", description="x")
    matrix.ARMS["ghost"] = arm
    try:
        with pytest.raises(matrix.HarnessError) as excinfo:
            matrix.resolve_arms(["ghost"])
        assert "not implemented" in str(excinfo.value)
        assert arm.pending_reason in str(excinfo.value)
    finally:
        del matrix.ARMS["ghost"]


def test_unknown_arm_refuses_and_lists_the_known_ones():
    with pytest.raises(matrix.HarnessError) as excinfo:
        matrix.resolve_arms(["llm_only:rag"])
    assert "unknown arm" in str(excinfo.value)
    assert "evagent" in str(excinfo.value)


def test_the_default_arms_are_the_implemented_rows_and_nothing_else():
    """Every default arm runs, and the two free reference arms are not among them."""
    assert all(matrix.ARMS[a].implemented for a in matrix.DEFAULT_ARMS)
    assert "optimum" not in matrix.DEFAULT_ARMS and "charge_asap" not in matrix.DEFAULT_ARMS


def test_react_is_evagent_with_the_gate_off():
    """The two agent rows share one code path and differ by the gate flag alone."""
    react, evagent = matrix.ARMS["react"], matrix.ARMS["evagent"]
    assert react.implemented and "react" in matrix.DEFAULT_ARMS
    assert (react.has_gate, evagent.has_gate) == (False, True)
    assert react.uses_llm == evagent.uses_llm and react.grounded == evagent.grounded
    assert react.scores_formulation == evagent.scores_formulation
    assert matrix.RUNNERS["react"].__name__ == "run_react_nogate"


# --------------------------------------------------------------------------- where output goes


def test_synthetic_run_refuses_to_write_inside_the_repository(tmp_path):
    """The one rule that keeps smoke-test traces out of the evidence directory."""
    inside = matrix.PROJECT_ROOT / "results" / "would_be_evidence"
    with pytest.raises(matrix.HarnessError) as excinfo:
        matrix.resolve_out_dir(str(inside), synthetic=True, model_slug="m", stamp="s")
    message = str(excinfo.value)
    assert "refusing to write a synthetic smoke test inside the repository" in message
    assert "data/benchmark/freeze.py" in message


def test_synthetic_default_directory_is_outside_the_repository(monkeypatch):
    """With no --out-dir, a synthetic run defaults outside the repo, not to the cwd.

    ``Path("")`` is ``Path(".")``, which is inside the repository for this
    project, so the default must be built from a real temporary root.
    """
    monkeypatch.delenv("EV_SMOKE_DIR", raising=False)
    path = matrix.resolve_out_dir(None, synthetic=True, model_slug="m", stamp="s")
    assert not matrix._is_inside(path, matrix.REPO_ROOT)
    assert "SYNTHETIC" in path.name


def test_real_run_defaults_inside_the_repository():
    """A real, paid run's traces are evidence and default into the repository."""
    path = matrix.resolve_out_dir(None, synthetic=False, model_slug="m", stamp="s")
    assert matrix._is_inside(path, matrix.REPO_ROOT)


def test_explicit_out_dir_outside_the_repo_is_accepted_for_a_synthetic_run(tmp_path):
    path = matrix.resolve_out_dir(str(tmp_path / "smoke"), synthetic=True, model_slug="m", stamp="s")
    assert not matrix._is_inside(path, matrix.REPO_ROOT)


# --------------------------------------------------------------------------- loud failure


def test_preflight_refuses_when_an_llm_arm_has_no_key(monkeypatch):
    """No key means no run. It must never mean a table with the LLM rows missing."""
    monkeypatch.setattr(matrix, "resolve_api_key", lambda provider: "")
    spec = matrix.parse_model_spec(MODEL)
    with pytest.raises(matrix.HarnessError) as excinfo:
        matrix.preflight(matrix.resolve_arms(["evagent"]), spec)
    message = str(excinfo.value)
    assert "OPENROUTER_API_KEY" in message
    assert "evagent" in message
    assert "silently" in message


def test_preflight_passes_without_a_key_when_no_arm_needs_one(monkeypatch):
    monkeypatch.setattr(matrix, "resolve_api_key", lambda provider: "")
    matrix.preflight(matrix.resolve_arms(["optimum", "charge_asap"]), matrix.parse_model_spec(MODEL))


def test_preflight_is_satisfied_by_an_injected_client(monkeypatch):
    """A stub client stands in for the key, which is what makes tests offline."""
    monkeypatch.setattr(matrix, "resolve_api_key", lambda provider: "")
    matrix.preflight(
        matrix.resolve_arms(["evagent"]), matrix.parse_model_spec(MODEL), client=StubClient()
    )


def test_a_failing_arm_becomes_a_failed_row_not_a_missing_one(requests_two_days, tmp_path, monkeypatch):
    """A crash is recorded as a row, keeps the ground truth, and fails the run."""

    def _boom(ctx):
        raise RuntimeError("solver exploded")

    monkeypatch.setitem(matrix.RUNNERS, "optimum", _boom)
    rows = matrix.run_matrix(
        arms=matrix.resolve_arms(["optimum"]),
        pairs=requests_two_days,
        spec=matrix.parse_model_spec(MODEL),
        model_requested=MODEL,
        out_dir=tmp_path,
        run_id="r",
        repeats=1,
        max_tool_rounds=1,
        max_completion_tokens=256,
        traceability_policy="grounded_only",
        ledger=matrix.Ledger(limit_usd=1.0),
        synthetic=True,
        data_source="fixture",
        inner_client=None,
        write_trace=False,
        progress=False,
    )
    assert len(rows) == len(requests_two_days)
    assert all(r["status"] == "failed" for r in rows)
    assert all("solver exploded" in r["error"] for r in rows)
    # The ground truth survives the failure, so the day can still be audited.
    assert all(r["answer_truth"] is not None for r in rows)
    summary = matrix.summarise(rows)
    assert summary[0]["n_failed"] == len(rows)
    assert summary[0]["solved"]["total"] == 0


def test_budget_ceiling_stops_the_run_and_marks_the_rest(requests_two_days, tmp_path):
    """Over budget is a recorded status, not an early return with a short table."""
    client = StubClient()
    ledger = matrix.Ledger(price_in=1000.0, price_out=1000.0, limit_usd=0.0001)
    rows = matrix.run_matrix(
        arms=matrix.resolve_arms(["llm_only:structured"]),
        pairs=requests_two_days,
        spec=matrix.parse_model_spec(MODEL),
        model_requested=MODEL,
        out_dir=tmp_path,
        run_id="r",
        repeats=1,
        max_tool_rounds=1,
        max_completion_tokens=256,
        traceability_policy="grounded_only",
        ledger=ledger,
        synthetic=True,
        data_source="fixture",
        inner_client=client,
        write_trace=False,
        progress=False,
    )
    assert len(rows) == len(requests_two_days)
    assert rows[-1]["status"] == "over_budget"
    assert "budget" in rows[-1]["error"].lower()


# --------------------------------------------------------------------------- the dry run


def test_dry_run_calls_nothing_and_writes_nothing(tmp_path, monkeypatch, capsys):
    """The estimate is read before anything is spent, so it must spend nothing."""
    monkeypatch.setattr(matrix, "build_client", lambda *a, **k: ExplodingClient())
    out_dir = tmp_path / "estimate"
    code = matrix.main(
        [
            "--dry-run",
            "--days", "2",
            "--out-dir", str(out_dir),
            "--model", MODEL,
        ]
    )
    assert code == 0
    assert not out_dir.exists()
    text = capsys.readouterr().out
    assert "DRY RUN" in text
    assert "TOTAL" in text
    assert "SMOKE TEST" in text


def test_dry_run_estimate_is_measured_from_the_real_prompt(requests_two_days):
    """The LLM arms' prompt tokens come from the prompt the runner would send."""
    estimates = {
        e["arm"]: e
        for e in matrix.estimate_run(
            matrix.resolve_arms(list(matrix.DEFAULT_ARMS) + ["optimum", "charge_asap"]),
            [r for _s, r in requests_two_days],
            repeats=1,
            price_in=2.5,
            price_out=10.0,
        )
    }
    assert estimates["optimum"]["usd"] == 0.0
    assert estimates["charge_asap"]["calls"] == 0
    for name in ("llm_only:structured", "llm_only:chain_of_thought", "evagent"):
        assert estimates[name]["prompt_tokens_per_call"] > 0
        assert estimates[name]["usd"] > 0
        assert estimates[name]["prompt_basis"]
    # Chain-of-thought adds a reasoning section, so its prompt is the longer one.
    assert (
        estimates["llm_only:chain_of_thought"]["prompt_tokens_per_call"]
        > estimates["llm_only:structured"]["prompt_tokens_per_call"]
    )


def test_estimate_scales_with_days_and_repeats(requests_two_days):
    """Doubling the repeats doubles the estimate; an estimate that did not would lie."""
    one = matrix.estimate_run(
        matrix.resolve_arms(["llm_only:structured"]),
        [r for _s, r in requests_two_days],
        repeats=1, price_in=2.5, price_out=10.0,
    )[0]
    two = matrix.estimate_run(
        matrix.resolve_arms(["llm_only:structured"]),
        [r for _s, r in requests_two_days],
        repeats=2, price_in=2.5, price_out=10.0,
    )[0]
    assert two["items"] == 2 * one["items"]
    assert two["usd"] == pytest.approx(2 * one["usd"])


# --------------------------------------------------------------------------- mechanical answers


@pytest.mark.parametrize("variant", [v for v in VARIANTS if v != "capacity_shortfall_cars"])
def test_rule_arms_answer_is_readable_by_the_scorer(variant):
    """A reference row's answer must go through the same extractor as a model's.

    Otherwise the two non-LLM rows would score wrong on the answer term for a
    reason that says nothing about them: that the harness phrased its own answer
    in a way its own extractor cannot read.
    """
    day = load_benchmark_requests(seed=0, dates=[date(2019, 4, 15)], source="fixture")[0].day
    try:
        request = build_request(day, seed=0, variant=variant, site_id="caltech", day_date="2019-04-15")
    except ValueError:
        pytest.skip(f"{variant} cannot be posed on this day")
    site, _tou = matrix.build_site_tou(request)
    schedule = matrix.charge_asap_schedule(request.day, float(site.get_P_max_at_step(0)))
    text = matrix.mechanical_answer_text(request, schedule)
    if request.checkable:
        assert extract_answer(text, request) is not None, f"{variant}: {text!r}"


# --------------------------------------------------------------------------- end to end


@pytest.fixture(scope="module")
def matrix_run(tmp_path_factory, requests_two_days):
    """One full offline run of every arm over two fixture days."""
    out_dir = tmp_path_factory.mktemp("ev_matrix_run")
    client = StubClient()
    client.day = requests_two_days[0][1].day
    rows = matrix.run_matrix(
        arms=matrix.resolve_arms(list(matrix.DEFAULT_ARMS) + ["optimum", "charge_asap"]),
        pairs=requests_two_days,
        spec=matrix.parse_model_spec(MODEL),
        model_requested=MODEL,
        out_dir=out_dir,
        run_id="ev_matrix_test_SYNTHETIC_SMOKE",
        repeats=1,
        max_tool_rounds=1,
        max_completion_tokens=512,
        traceability_policy="grounded_only",
        ledger=matrix.Ledger(price_in=2.5, price_out=10.0, limit_usd=10.0),
        synthetic=True,
        data_source="fixture",
        inner_client=client,
        write_trace=True,
        progress=False,
    )
    return out_dir, rows, client


def test_every_arm_produced_a_row_for_every_day(matrix_run, requests_two_days):
    _out_dir, rows, _client = matrix_run
    # the fixture runs the defaults plus the two free arms the harness tests use
    arms = list(matrix.DEFAULT_ARMS) + ["optimum", "charge_asap"]
    assert len(rows) == len(arms) * len(requests_two_days)
    by_arm = {}
    for row in rows:
        by_arm.setdefault(row["arm"], []).append(row)
    assert set(by_arm) == set(arms)
    for arm, arm_rows in by_arm.items():
        assert len(arm_rows) == len(requests_two_days), arm


def test_rows_have_exactly_the_declared_fields(matrix_run):
    """The CSV schema is fixed, so a row can never quietly gain or lose a column."""
    _out_dir, rows, _client = matrix_run
    for row in rows:
        assert list(row.keys()) == list(matrix.ROW_FIELDS)


def test_every_arm_saw_the_same_requests(matrix_run):
    """Fairness is checked on the artefacts, not asserted in the docstring."""
    _out_dir, rows, _client = matrix_run
    digests = {row["requests_digest"] for row in rows}
    assert len(digests) == 1
    by_arm: Dict[str, set] = {}
    for row in rows:
        by_arm.setdefault(row["arm"], set()).add(row["request_id"])
    assert len({frozenset(ids) for ids in by_arm.values()}) == 1


def test_both_answers_are_on_every_row_including_state_requests(matrix_run):
    """The value the power-flow study threw away is kept on every row here."""
    _out_dir, rows, _client = matrix_run
    ok_rows = [r for r in rows if r["status"] == "ok"]
    assert ok_rows
    for row in ok_rows:
        assert row["answer_truth"] is not None, row["request_id"]
        assert "answer_given" in row
    state_rows = [r for r in ok_rows if r["answer_kind"] == "state"]
    for row in state_rows:
        # Not compared, but stored: the resulting-state summary is still there.
        assert isinstance(row["answer_truth"], dict)
        assert row["answer_status"] == "not_checkable"


def test_llm_rows_record_the_resolved_model_and_the_prompt_hash(matrix_run):
    """A row must say which model answered and what was actually sent to it."""
    _out_dir, rows, _client = matrix_run
    llm_rows = [
        r for r in rows if matrix.ARMS[r["arm"]].uses_llm and r["status"] == "ok"
    ]
    assert llm_rows
    for row in llm_rows:
        assert row["model_resolved"] == "openai/gpt-4o-2024-11-20"
        assert row["model_resolved"] != row["model_spec"]
        assert str(row["prompt_hash"]).startswith("sha256:")
        assert str(row["system_prompt_hash"]).startswith("sha256:")
        assert row["prompt_tokens"] > 0


def test_no_tools_rows_carry_the_parser_repair_counts(matrix_run):
    """How often a reply had to be repaired to be scorable is a reportable finding."""
    _out_dir, rows, _client = matrix_run
    no_tools = [r for r in rows if r["arm"].startswith("llm_only") and r["status"] == "ok"]
    assert no_tools
    for row in no_tools:
        assert row["repairs_changed"] in (True, False)
        assert row["parse_success"] in (True, False)
        for kind in matrix.REPAIR_KINDS:
            assert row[f"repair_{kind}"] is not None
        assert row["repair_negative_cells"] is not None


def test_non_llm_rows_do_not_pretend_to_have_a_model(matrix_run):
    _out_dir, rows, _client = matrix_run
    for row in rows:
        if not matrix.ARMS[row["arm"]].uses_llm:
            assert row["n_llm_calls"] == 0
            assert row["est_cost_usd"] == 0.0


def test_the_optimum_row_has_no_cost_gap(matrix_run):
    """The reference row is the denominator, so its gap is zero by construction."""
    _out_dir, rows, _client = matrix_run
    optimum = [r for r in rows if r["arm"] == "optimum" and r["status"] == "ok"]
    assert optimum
    for row in optimum:
        assert row["gap_pct"] == pytest.approx(0.0, abs=1e-6)
        assert row["no_hard_violation"] is True


def test_terms_an_arm_does_not_expose_are_not_checkable_not_passing(matrix_run):
    """`n/a` must never be stored as a pass: that is how a baseline flatters itself."""
    _out_dir, rows, _client = matrix_run
    for row in rows:
        if row["status"] != "ok":
            continue
        arm = matrix.ARMS[row["arm"]]
        if not arm.scores_formulation:
            assert row["formulation_status"] == "not_checkable"
        if not arm.uses_llm:
            assert row["traceability_status"] == "not_checkable"
        if not arm.has_gate:
            assert not row["escalated"]


def test_formulation_rows_carry_their_own_denominator(matrix_run):
    """A per-session rate is only re-derivable if both counts are on the row."""
    _out_dir, rows, _client = matrix_run
    scored = [
        r for r in rows
        if r["status"] == "ok" and r["formulation_status"] in ("pass", "fail")
    ]
    assert scored
    for row in scored:
        assert row["n_sessions_truth"] == row["n_sessions"]
        assert row["n_sessions_parsed"] is not None
        assert 0 <= row["n_sessions_exact"] <= row["n_sessions_truth"]


# --------------------------------------------------------------------------- formulation


def _formulation_rows(exact_and_truth, **extra):
    """Rows of one arm carrying only what the Formulation columns read."""
    return [
        {
            "arm": "evagent",
            "arm_label": "EVAgent",
            "status": "ok",
            "formulation_status": "pass" if exact == truth else "fail",
            "n_sessions_exact": exact,
            "n_sessions_truth": truth,
            "n_sessions": truth,
            **extra,
        }
        for exact, truth in exact_and_truth
    ]


def test_formulation_is_reported_per_session():
    """Table S3's definition: sessions extracted correctly over ground-truth sessions."""
    summary = matrix.summarise(_formulation_rows([(40, 44), (8, 10)]))

    assert summary[0]["formulation_exact"] == {"rate": 48 / 54, "count": 48, "total": 54}


def test_a_day_with_most_sessions_right_does_not_print_zero():
    """The defect this column had: one wrong car out of 43 scored the day as 0.

    The per-day verdict is kept beside the per-session rate rather than dropped,
    because it is the right number for a different question. It is not the
    number the supplement promises.
    """
    summary = matrix.summarise(_formulation_rows([(42, 43)]))

    assert summary[0]["formulation_exact"]["rate"] == pytest.approx(42 / 43)
    assert summary[0]["formulation_days"] == {"rate": 0.0, "count": 0, "total": 1}


def test_a_perfect_day_passes_both_formulation_columns():
    """The two columns agree exactly when every session of every day is exact."""
    summary = matrix.summarise(_formulation_rows([(43, 43), (10, 10)]))

    assert summary[0]["formulation_exact"]["rate"] == 1.0
    assert summary[0]["formulation_days"]["rate"] == 1.0


def test_an_arm_with_no_extraction_step_measures_neither_column():
    """`n/a (0/0)` on both, which is not the same as a formulation of zero."""
    rows = [
        {
            "arm": "llm_only:structured",
            "arm_label": "LLM-only",
            "status": "ok",
            "formulation_status": "not_checkable",
            "n_sessions_exact": None,
            "n_sessions_truth": None,
            "n_sessions": 44,
        }
    ]
    summary = matrix.summarise(rows)

    assert summary[0]["formulation_exact"] == {"rate": None, "count": 0, "total": 0}
    assert summary[0]["formulation_days"] == {"rate": None, "count": 0, "total": 0}


def test_a_failed_day_is_in_no_formulation_denominator():
    """A crashed day cannot quietly improve the column it never reached."""
    rows = _formulation_rows([(40, 44)]) + [
        {
            "arm": "evagent",
            "arm_label": "EVAgent",
            "status": "failed",
            "formulation_status": None,
            "n_sessions_exact": None,
            "n_sessions_truth": None,
            "n_sessions": 30,
        }
    ]
    summary = matrix.summarise(rows)

    assert summary[0]["n_failed"] == 1
    assert summary[0]["formulation_exact"]["total"] == 44


def test_the_scoreboard_prints_both_formulation_columns():
    """A reader must be able to see which of the two a cell is."""
    summary = matrix.summarise(_formulation_rows([(40, 44)]))
    text = matrix.scoreboard_markdown(summary, {"synthetic": False})

    assert "| Form. | Form. days |" in text
    assert "90.9% (40/44)" in text
    assert "0.0% (0/1)" in text
    assert "`Form.` is per session" in text


def test_the_manifest_states_what_the_moving_columns_meant():
    """A directory has to say which definitions produced its numbers."""
    assert matrix.FORMULATION_AGGREGATION == "per_session"
    assert "formulation" not in matrix.SOLVED_TERMS


def test_gate_conditions_are_on_the_agent_rows(matrix_run):
    """The gate's per-condition row travels with the day it judged."""
    _out_dir, rows, _client = matrix_run
    agent_rows = [r for r in rows if r["arm"] == "evagent" and r["status"] == "ok"]
    assert agent_rows
    assert any(
        any(row[name] is not None for name in matrix.GATE_ROW_FIELDS) for row in agent_rows
    )


# --------------------------------------------------------------------------- artefacts


@pytest.fixture(scope="module")
def written_run(matrix_run):
    """The run's rows written out, with the scoreboard and manifest beside them."""
    out_dir, rows, _client = matrix_run
    summary = matrix.summarise(rows)
    meta = {
        "run_id": "ev_matrix_test_SYNTHETIC_SMOKE",
        "created_at": "2026-09-19T00:00:00+00:00",
        "synthetic": True,
        "smoke_test": True,
        "data_source": "fixture",
        "site_id": "caltech",
        "dates": sorted({r["date"] for r in rows}),
        "n_days": len({r["date"] for r in rows}),
        "seeds": [0],
        "repeats": 1,
        "items_per_arm": 2,
        "arms": list(matrix.DEFAULT_ARMS),
        "pending_arms": {
            name: arm.pending_reason for name, arm in matrix.ARMS.items() if not arm.implemented
        },
        "model_requested": MODEL,
        "model_spec": MODEL,
        "models_resolved": sorted({r["model_resolved"] for r in rows if r["model_resolved"]}),
        "max_completion_tokens": 512,
        "max_tool_rounds": 1,
        "traceability_policy": "grounded_only",
        "gap_tol_pct": matrix.GAP_TOL_PCT,
        "budget_usd": 10.0,
        "spent_usd": 0.01,
        "price_in_per_mtok": 2.5,
        "price_out_per_mtok": 10.0,
        "price_source": "test",
        "requests_digest": rows[0]["requests_digest"],
        "strategies": {},
        "python": "3.14",
        "n_failed": sum(1 for r in rows if r["status"] != "ok"),
        "out_dir": str(out_dir),
    }
    matrix.write_rows(out_dir, rows)
    matrix.write_scoreboard(out_dir, summary, meta)
    matrix.write_manifest(out_dir, meta)
    matrix.write_smoke_sentinel(out_dir, meta)
    return out_dir, rows, summary, meta


def test_rows_are_written_as_both_csv_and_jsonl(written_run):
    out_dir, rows, _summary, _meta = written_run
    csv_text = (out_dir / "rows.csv").read_text(encoding="utf-8")
    jsonl_lines = (out_dir / "rows.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(jsonl_lines) == len(rows)
    assert csv_text.splitlines()[0].startswith("run_id,arm,arm_label")
    restored = [json.loads(line) for line in jsonl_lines]
    assert all(list(r.keys()) == list(matrix.ROW_FIELDS) for r in restored)


def test_traces_land_under_the_run_directory(matrix_run):
    """Traces follow the output directory, which is what places them correctly."""
    out_dir, _rows, _client = matrix_run
    traces = list((out_dir / "traces").rglob("*.json"))
    assert traces
    for path in traces:
        assert matrix._is_inside(path, out_dir)


def test_scoreboard_says_smoke_test_and_carries_denominators(written_run):
    out_dir, _rows, _summary, _meta = written_run
    text = (out_dir / "scoreboard.md").read_text(encoding="utf-8")
    assert "SMOKE TEST" in text
    assert "DO NOT CITE" in text
    assert "SYNTHETIC" in text
    # Every rate cell carries (count/total).
    assert "/2)" in text or "(0/0)" in text
    assert (out_dir / matrix.SMOKE_SENTINEL_NAME).exists()
    sentinel = (out_dir / matrix.SMOKE_SENTINEL_NAME).read_text(encoding="utf-8")
    assert store.SYNTHETIC_WARNING in sentinel


def test_scoreboard_csv_splits_rate_from_denominator(written_run):
    out_dir, _rows, _summary, _meta = written_run
    text = (out_dir / "scoreboard.csv").read_text(encoding="utf-8")
    header = text.splitlines()[0]
    for name in (
        "solved_rate", "solved_count", "solved_total", "smoke_test_synthetic_data",
        "formulation_rate", "formulation_total",
        "formulation_days_rate", "formulation_days_total",
    ):
        assert name in header


def test_report_states_the_protocol_and_the_warning(written_run):
    """REPORT.md is the artefact a reader sees, so the warning has to be in it."""
    out_dir, _rows, _summary, _meta = written_run
    code = ev_report.main([str(out_dir)])
    assert code == 0
    text = (out_dir / "REPORT.md").read_text(encoding="utf-8")
    assert text.startswith("# [SMOKE TEST - SYNTHETIC DATA]")
    assert "DO NOT CITE" in text
    for title in ev_report.SECTION_TITLES:
        assert title in text
    # The protocol, stated with the evidence for it.
    assert "requests_digest" in text
    assert "openai/gpt-4o-2024-11-20" in text
    # Denominators, and the rule about what n/a means.
    assert "n/a (0/0)" in text or "(0/0)" in text
    assert "is not a pass" in text
    # The pending rows are named rather than silently absent.
    assert "react" in text and "plan_act" in text


def test_report_refuses_a_directory_that_is_not_a_run(tmp_path, capsys):
    assert ev_report.main([str(tmp_path)]) == 2
    assert "not a run_ev_matrix results directory" in capsys.readouterr().err


def test_report_flags_a_split_prompt_or_a_moved_alias(written_run):
    """The two incidents the repo has already had, detected from the rows."""
    out_dir, rows, summary, meta = written_run
    spliced = [dict(r) for r in rows]
    spliced[0]["system_prompt_hash"] = "sha256:deadbeef"
    spliced[1]["system_prompt_hash"] = "sha256:feedface"
    meta2 = dict(meta)
    meta2["models_resolved"] = ["openai/gpt-4o-2024-08-06", "openai/gpt-4o-2024-11-20"]
    text = ev_report.section_caveats(meta2, summary, spliced)
    assert "distinct system-prompt hashes" in text
    assert "distinct resolved model ids" in text


# --------------------------------------------------------------------------- concurrency


class Gate:
    """Holds every caller inside it until ``width`` of them are in at once.

    A concurrency test that only sleeps proves nothing: on a busy machine a
    serial runner can look parallel and a parallel one can look serial. This
    makes the assertion a statement about the pool. ``width`` callers all have
    to be inside before any of them leaves, so ``max_in_flight`` reaches
    ``width`` if and only if that many items really ran at the same time, and a
    serial runner leaves it at 1 after the timeout instead of hanging.

    Attributes:
        max_in_flight: The largest number of callers that were inside together.
    """

    def __init__(self, width: int, timeout: float = 5.0) -> None:
        self.width = int(width)
        self.max_in_flight = 0
        self._timeout = float(timeout)
        self._in_flight = 0
        self._cond = threading.Condition()

    @contextlib.contextmanager
    def hold(self):
        """Enter the gate, wait for the others, run the body, and leave."""
        with self._cond:
            self._in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self._in_flight)
            self._cond.notify_all()
            deadline = time.monotonic() + self._timeout
            while self._in_flight < self.width and time.monotonic() < deadline:
                self._cond.wait(timeout=0.05)
        try:
            yield
        finally:
            with self._cond:
                self._in_flight -= 1
                self._cond.notify_all()


class GatedStubClient(StubClient):
    """A stub whose calls are held open until several items are in flight.

    It is how the budget test puts the harness in the state a ceiling has to
    survive: several calls made, none of them returned, so nothing has been
    added to the ledger yet and only the reservations stand between the run and
    the ceiling. While it holds them it samples what the ledger has committed,
    which is the quantity that must never pass the ceiling.

    Attributes:
        gate: The gate the calls are held in.
        committed: What the ledger had committed as each call went in.
    """

    def __init__(self, *, width: int, ledger: Optional[Any] = None,
                 timeout: float = 5.0, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.gate = Gate(width, timeout=timeout)
        self.ledger = ledger
        self.committed: List[float] = []

    def respond(self, **kwargs: Any) -> Any:
        with self.gate.hold():
            if self.ledger is not None:
                self.committed.append(self.ledger.committed_usd())
            return super().respond(**kwargs)


class ThreadNamingStubClient(StubClient):
    """A stub that remembers which threads called it, so a claim about the pool
    can be checked rather than assumed."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.threads: set = set()

    def respond(self, **kwargs: Any) -> Any:
        self.threads.add(threading.current_thread().name)
        return super().respond(**kwargs)


def _run(pairs, out_dir: Path, *, arms, ledger, client=None, workers=1, repeats=1):
    """One offline matrix run, with everything but the scheduler held fixed."""
    return matrix.run_matrix(
        arms=matrix.resolve_arms(arms),
        pairs=pairs,
        spec=matrix.parse_model_spec(MODEL),
        model_requested=MODEL,
        out_dir=out_dir,
        run_id="ev_matrix_test_SYNTHETIC_SMOKE",
        repeats=repeats,
        max_tool_rounds=1,
        max_completion_tokens=512,
        traceability_policy="grounded_only",
        ledger=ledger,
        synthetic=True,
        data_source="fixture",
        inner_client=client,
        write_trace=False,
        progress=False,
        workers=workers,
    )


def _order(rows) -> List[tuple]:
    """The identity of every row, in the order the rows came out."""
    return [(r["arm"], r["date"], r["seed"], r["repeat"]) for r in rows]


# -- the flag ---------------------------------------------------------------


def test_the_serial_path_is_the_default():
    """Concurrency is opt-in: the tested path is the one that runs by default."""
    assert matrix.DEFAULT_WORKERS == 1
    assert matrix.build_parser().parse_args([]).workers == 1
    assert matrix.build_parser().parse_args(["--workers", "5"]).workers == 5


def test_workers_below_one_is_refused(capsys):
    assert matrix.main(["--workers", "0", "--dry-run", "--days", "1"]) == 2
    assert "--workers must be at least 1" in capsys.readouterr().err


# -- the budget -------------------------------------------------------------


def test_the_reservation_is_the_dry_run_estimate_for_one_item(requests_two_days):
    """One item's reservation is one item's share of the number --dry-run prints.

    The reservation has to be argued with the same way the estimate is, so it is
    built from the same measured prompt and the same arm cost model rather than
    from a second guess that could drift from it.
    """
    ledger = matrix.Ledger(price_in=2.5, price_out=10.0, limit_usd=1.0)
    arm = matrix.ARMS["llm_only:structured"]
    per_item = [matrix.estimate_item_cost(arm, r, ledger) for _s, r in requests_two_days]
    whole = matrix.estimate_run(
        [arm], [r for _s, r in requests_two_days], repeats=1, price_in=2.5, price_out=10.0
    )[0]
    assert all(cost > 0 for cost in per_item)
    assert sum(per_item) == pytest.approx(whole["usd"], rel=1e-3)
    assert matrix.estimate_item_cost(matrix.ARMS["optimum"], requests_two_days[0][1], ledger) == 0.0


def test_a_reservation_counts_until_the_item_reconciles_it():
    """While an item runs the ledger counts its estimate, not its spend so far."""
    ledger = matrix.Ledger(price_in=1.0, price_out=1.0, limit_usd=10.0)
    reservation = ledger.reserve("item-1", 1.0)
    assert ledger.committed_usd() == pytest.approx(1.0)
    ledger.add(100_000, 0, reservation=reservation)  # $0.10 of the $1.00 claim
    assert ledger.spent_usd == pytest.approx(0.1)
    assert ledger.committed_usd() == pytest.approx(1.0)
    assert ledger.release(reservation) == pytest.approx(0.1)
    assert ledger.committed_usd() == pytest.approx(0.1)


def test_reservations_in_flight_cannot_commit_more_than_the_ceiling():
    """Eight threads claiming at once commit no more between them than the ceiling."""
    ledger = matrix.Ledger(price_in=1.0, price_out=1.0, limit_usd=1.0)
    granted: List[matrix.Reservation] = []
    refused: List[str] = []
    lock = threading.Lock()
    start = threading.Barrier(8)

    def _claim(index: int) -> None:
        start.wait(timeout=5.0)
        try:
            reservation = ledger.reserve(f"item-{index}", 0.3)
        except matrix.BudgetExceeded as exc:
            with lock:
                refused.append(str(exc))
            return
        with lock:
            granted.append(reservation)

    threads = [threading.Thread(target=_claim, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10.0)

    assert len(granted) == 3  # 4 x 0.3 would reach 1.2, over the $1.00 ceiling
    assert len(refused) == 5
    assert ledger.committed_usd() == pytest.approx(0.9)
    assert all("budget ceiling would be passed" in message for message in refused)


def test_the_budget_ceiling_holds_with_several_items_in_flight(requests_two_days, tmp_path):
    """The defect this exists for: N calls in flight must not pass the ceiling.

    Adding a cost once an item has returned is not a ceiling when items overlap.
    The stub holds three calls open at once, so nothing has reached the ledger
    when the fourth item asks to launch and only its reservation can refuse it.
    The stub also reports tokens close to what the estimate assumed, which is
    what makes the outcome independent of who finishes first: three items commit
    about $0.073 whether they are running or already paid for, and a fourth
    claim crosses $0.08 either way.
    """
    ledger = matrix.Ledger(price_in=2.5, price_out=10.0, limit_usd=0.08)
    client = GatedStubClient(
        width=3, ledger=ledger, timeout=5.0, prompt_tokens=900, completion_tokens=2200,
    )
    client.day = requests_two_days[0][1].day
    arm = matrix.ARMS["llm_only:structured"]
    per_item = max(matrix.estimate_item_cost(arm, r, ledger) for _s, r in requests_two_days)
    assert 3 * per_item < 0.08 <= 4 * per_item  # the ceiling this run is aimed at

    rows = _run(
        requests_two_days, tmp_path,
        arms=["llm_only:structured"], ledger=ledger, client=client, workers=8, repeats=5,
    )

    assert len(rows) == len(requests_two_days) * 5
    ran = [r for r in rows if r["status"] == "ok"]
    blocked = [r for r in rows if r["status"] == "over_budget"]
    assert client.gate.max_in_flight >= 2, "the items did not actually overlap"
    # Never, at any moment and with any number of them in flight, over the ceiling.
    assert client.committed, "no call was observed"
    assert max(client.committed) <= 0.08
    assert len(ran) == 3
    assert len(blocked) == len(rows) - 3
    assert ledger.spent_usd <= 0.08
    assert ledger.committed_usd() == pytest.approx(ledger.spent_usd)  # every claim released
    assert any("budget ceiling would be passed" in (r["error"] or "") for r in blocked)
    # A blocked row is still a row, with its day and its ground truth on it.
    assert all(r["answer_truth"] is not None for r in blocked)


def test_an_item_that_overspends_while_running_stops_the_run(requests_two_days, tmp_path):
    """The other half of the ceiling: a claim can be too small, and then the
    guard inside the call has to stop the run at the next call.

    A reservation is an estimate. An item whose real cost runs past it is caught
    mid-flight, its own row says so, and everything not yet launched is marked
    rather than quietly dropped.
    """
    client = StubClient(prompt_tokens=60_000_000, completion_tokens=0)
    client.day = requests_two_days[0][1].day
    ledger = matrix.Ledger(price_in=2.5, price_out=10.0, limit_usd=0.10)
    arm = matrix.ARMS["evagent"]
    assert all(
        matrix.estimate_item_cost(arm, r, ledger) < 0.10 for _s, r in requests_two_days
    )  # every item's claim fits; only the real spend does not

    rows = _run(
        requests_two_days, tmp_path,
        arms=["evagent"], ledger=ledger, client=client, workers=4, repeats=1,
    )

    assert len(rows) == len(requests_two_days)
    assert all(r["status"] == "over_budget" for r in rows)
    assert any("budget ceiling reached" in (r["error"] or "") for r in rows)
    assert ledger.committed_usd() == pytest.approx(ledger.spent_usd)


# -- failure isolation ------------------------------------------------------


def test_one_item_raising_does_not_lose_the_others(requests_two_days, tmp_path, monkeypatch):
    """A worker that dies must cost its own row and nothing else's."""
    gate = Gate(width=2, timeout=5.0)
    doomed = requests_two_days[0][1].date

    def _sometimes_boom(ctx):
        with gate.hold():
            if ctx.request.date == doomed:
                raise RuntimeError("solver exploded")
            return matrix.run_optimum(ctx)

    monkeypatch.setitem(matrix.RUNNERS, "optimum", _sometimes_boom)
    rows = _run(
        requests_two_days, tmp_path,
        arms=["optimum"], ledger=matrix.Ledger(limit_usd=1.0), workers=4, repeats=3,
    )

    assert len(rows) == len(requests_two_days) * 3
    failed = [r for r in rows if r["status"] == "failed"]
    survived = [r for r in rows if r["status"] == "ok"]
    assert len(failed) == 3
    assert len(survived) == 3
    assert gate.max_in_flight >= 2, "the items did not actually overlap"
    assert all("solver exploded" in r["error"] for r in failed)
    assert all(r["date"] == doomed for r in failed)
    assert all(r["answer_truth"] is not None for r in failed)
    assert all(r["outcome"] for r in survived)


# -- determinism ------------------------------------------------------------


def test_rows_are_ordered_by_arm_then_date_then_seed_then_repeat(tmp_path):
    """The run's order is the matrix's, not the arrival order of the threads."""
    pairs = matrix.load_requests(
        seeds=[1, 0], dates=SUBSET_DATES, site_id="caltech", source="fixture"
    )
    rows = _run(
        pairs, tmp_path,
        arms=["charge_asap", "optimum"], ledger=matrix.Ledger(limit_usd=1.0),
        workers=4, repeats=2,
    )
    order = _order(rows)
    # Arms in the order they were asked for, and never reordered by the pool.
    assert [name for name, _d, _s, _r in order] == ["charge_asap"] * 8 + ["optimum"] * 8
    for arm in ("charge_asap", "optimum"):
        within = [(d, s, r) for name, d, s, r in order if name == arm]
        assert within == sorted(within)
        assert len(set(within)) == len(within)


def test_workers_do_not_change_a_single_byte_of_the_artefacts(requests_two_days, tmp_path):
    """Four workers and one worker write the same files, byte for byte.

    This is the whole claim of ``--workers``: a reader of a results directory
    cannot tell how it was scheduled, so the flag is a wall-clock decision and
    never an evidence decision. Only ``wall_s`` is neutralised, because it
    measures the run and not the result.
    """
    serial_dir = tmp_path / "serial"
    parallel_dir = tmp_path / "parallel"
    artefacts = {}
    threads = {}
    for name, out_dir, workers in (("serial", serial_dir, 1), ("parallel", parallel_dir, 4)):
        client = ThreadNamingStubClient()
        client.day = requests_two_days[0][1].day
        ledger = matrix.Ledger(price_in=2.5, price_out=10.0, limit_usd=10.0)
        rows = _run(
            requests_two_days, out_dir,
            arms=None, ledger=ledger, client=client, workers=workers, repeats=2,
        )
        artefacts[name] = _write_artefacts(out_dir, rows, ledger)
        threads[name] = client.threads

    # The comparison is only worth anything if the two runs really differed.
    assert len(threads["serial"]) == 1
    assert len(threads["parallel"]) > 1
    assert artefacts["serial"].keys() == artefacts["parallel"].keys()
    for filename in sorted(artefacts["serial"]):
        assert artefacts["serial"][filename] == artefacts["parallel"][filename], filename


def _write_artefacts(out_dir: Path, rows, ledger) -> Dict[str, bytes]:
    """Write every artefact of a finished run and return them as bytes.

    ``wall_s`` is zeroed first. It is the one field that cannot be stable across
    two runs of the same matrix, serial or not, because it times the machine.
    """
    fixed = []
    for row in rows:
        entry = dict(row)
        entry["wall_s"] = 0.0
        fixed.append(entry)
    summary = matrix.summarise(fixed)
    meta = {
        "run_id": "ev_matrix_test_SYNTHETIC_SMOKE",
        "created_at": "2026-09-19T00:00:00+00:00",
        "synthetic": True,
        "smoke_test": True,
        "data_source": "fixture",
        "site_id": "caltech",
        "dates": sorted({r["date"] for r in fixed}),
        "n_days": len({r["date"] for r in fixed}),
        "seeds": [0],
        "repeats": 2,
        "items_per_arm": len(fixed) // len(matrix.DEFAULT_ARMS),
        "arms": list(matrix.DEFAULT_ARMS),
        "model_requested": MODEL,
        "model_spec": MODEL,
        "models_resolved": sorted({r["model_resolved"] for r in fixed if r["model_resolved"]}),
        "traceability_policy": "grounded_only",
        "budget_usd": 10.0,
        "spent_usd": round(ledger.spent_usd, 6),
        "prompt_tokens": ledger.prompt_tokens,
        "completion_tokens": ledger.completion_tokens,
        "n_llm_calls": ledger.n_calls,
        "price_in_per_mtok": 2.5,
        "price_out_per_mtok": 10.0,
        "requests_digest": fixed[0]["requests_digest"],
        "n_failed": sum(1 for r in fixed if r["status"] != "ok"),
    }
    matrix.write_rows(out_dir, fixed)
    matrix.write_scoreboard(out_dir, summary, meta)
    matrix.write_manifest(out_dir, meta)
    names = ["rows.csv", "rows.jsonl", "scoreboard.md", "scoreboard.csv", "scoreboard.json",
             "run_manifest.json"]
    return {name: (out_dir / name).read_bytes() for name in names}


# -- incremental rows -------------------------------------------------------


def test_each_row_reaches_the_disk_as_it_is_scored(requests_two_days, tmp_path, monkeypatch):
    """A killed run keeps its scored rows, not only its traces.

    Every item looks at ``rows.jsonl`` before it starts. Item k sees the k rows
    that finished before it, which is only true if the rows are appended as they
    complete. With the old end-of-run write every item would have seen nothing.
    """
    seen: List[int] = []
    rows_path = tmp_path / "rows.jsonl"

    def _watching(ctx):
        text = rows_path.read_text(encoding="utf-8") if rows_path.exists() else ""
        seen.append(len([line for line in text.splitlines() if line.strip()]))
        return matrix.run_optimum(ctx)

    monkeypatch.setitem(matrix.RUNNERS, "optimum", _watching)
    rows = _run(
        requests_two_days, tmp_path,
        arms=["optimum"], ledger=matrix.Ledger(limit_usd=1.0), workers=1, repeats=3,
    )
    assert seen == list(range(len(rows)))
    written = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    assert _order(written) == _order(rows)


def test_a_run_stopped_part_way_leaves_the_rows_it_had_scored(requests_two_days, tmp_path, monkeypatch):
    """The point of appending: what was scored before the kill is still there."""
    rows_path = tmp_path / "rows.jsonl"
    done = 0

    def _dies_on_the_third(ctx):
        nonlocal done
        if done == 2:
            raise KeyboardInterrupt("killed")
        done += 1
        return matrix.run_optimum(ctx)

    monkeypatch.setitem(matrix.RUNNERS, "optimum", _dies_on_the_third)
    with pytest.raises(KeyboardInterrupt):
        _run(
            requests_two_days, tmp_path,
            arms=["optimum"], ledger=matrix.Ledger(limit_usd=1.0), workers=1, repeats=3,
        )
    written = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    assert len(written) == 2
    assert all(r["status"] == "ok" for r in written)
    assert all(list(r.keys()) == list(matrix.ROW_FIELDS) for r in written)


# -- end to end -------------------------------------------------------------


def test_a_parallel_run_writes_a_sorted_file_and_a_manifest_that_does_not_say_so(
    tmp_path, monkeypatch
):
    """``--workers`` end to end: same artefacts, and the manifest keeps the protocol.

    The manifest states what was compared, not how the comparison was scheduled.
    A ``workers`` key in it would let a reader think the number mattered to the
    result, which is exactly what the ordering rule exists to deny.
    """
    client = StubClient()
    client.day = load_benchmark_requests(
        seed=0, dates=[store.BENCHMARK_DATES[0]], source="fixture"
    )[0].day
    monkeypatch.setattr(matrix, "build_client", lambda *a, **k: client)
    monkeypatch.setattr(matrix, "resolve_api_key", lambda provider: "test-key")
    out_dir = tmp_path / "parallel_run"
    code = matrix.main(
        ["--days", "2", "--out-dir", str(out_dir), "--model", MODEL,
         "--workers", "4", "--no-trace", "--quiet", "--budget-usd", "10"]
    )
    assert code == 0
    rows = [json.loads(line) for line in (out_dir / "rows.jsonl").read_text().splitlines()]
    assert len(rows) == 2 * len(matrix.DEFAULT_ARMS)
    assert [r["arm"] for r in rows] == [a for a in matrix.DEFAULT_ARMS for _ in range(2)]
    for arm in matrix.DEFAULT_ARMS:
        dates = [r["date"] for r in rows if r["arm"] == arm]
        assert dates == sorted(dates)
    manifest = json.loads((out_dir / "run_manifest.json").read_text())
    assert "workers" not in manifest
    assert manifest["items_per_arm"] == 2
