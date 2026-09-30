"""An account outage must stop a run; a model limit must not.

The distinction these tests pin down is the one that cost us a morning on 2026-09-29: the runner's
`except Exception` recorded every provider failure the same way and moved on to the next item, so a
run that lost the account at request 5 still ended with a summary of 20 rows that read as measured.
A 402 says nothing about the method under test and will repeat on every remaining item. A 400 for
context length is a property of the request and belongs in the table."""

from evaluation.runner import ProviderOutage, provider_outage


CONTEXT_400 = (
    "RuntimeError: LLM request failed: BadRequestError: Error code: 400 - {'error': {'message': "
    "'Provider returned error', 'code': 400, 'metadata': {'raw': '{\\n \"error\": {\\n \"message\": "
    "\"This model's maximum context length is 128000 tokens. However, you requested 141360 tokens "
    "(124976 in the messages, 16384 in the completion). Please reduce the length of the messages or "
    "completion.\",\\n \"code\": \"context_length_exceeded\"\\n }\\n}'}}}"
)
CREDIT_402 = (
    "RuntimeError: LLM request failed: APIStatusError: Error code: 402 - {'error': {'message': "
    "'This request would exceed your available credits given your current in-flight requests', "
    "'code': 402}}"
)


def test_credit_exhaustion_is_an_outage():
    assert provider_outage(CREDIT_402) == "available credits"


def test_context_length_is_not_an_outage():
    """The 7 run_errors of ieee300/gpt-4o-mini/pfagent are these. They are results: the accumulated
    conversation plus the reserved completion do not fit in 128k. Dropping them would delete the
    measurement that motivates the context-budget guard."""
    assert provider_outage(CONTEXT_400) is None


def test_a_400_that_mentions_billing_is_still_not_an_outage():
    """Order matters: the 400 check runs before the marker scan, so provider prose cannot promote a
    request-level failure into an account-level one."""
    assert provider_outage("Error code: 400 - your billing tier limits this model") is None


def test_ordinary_failures_pass_through():
    for err in (
        "RuntimeError: LLM request failed: APIConnectionError: Connection error.",
        "RuntimeError: no_solver_result: the method produced no power-flow state to score",
        "Error code: 429 - rate limit exceeded",
        "",
        None,
    ):
        assert provider_outage(err) is None, err


def test_auth_failures_are_outages():
    assert provider_outage("Error code: 401 - No auth credentials found") is not None
    assert provider_outage("insufficient_quota: you exceeded your current quota") is not None


def test_outage_is_not_a_plain_runtime_error_by_accident():
    """It must be catchable on its own in main(), not swallowed by a broad `except RuntimeError`
    that also catches no_solver_result."""
    assert issubclass(ProviderOutage, RuntimeError)
    assert ProviderOutage is not RuntimeError


# ------------------------------------------------------------------ the loop actually stops

import json

import pytest

from evaluation.runner import run_benchmark
from solver.power_flow import SolverConfig
from tests.test_benchmark_runner import FAKE_MODEL, PRICING, _resp


class _DiesOnCredit:
    """Answers the first item, then loses the account, exactly as the shared key did on
    2026-09-29 when four sessions drew it down to 1.69 USD."""

    def __init__(self, fail_after=1):
        self.calls = 0
        self.fail_after = fail_after

    def create(self, **kwargs):
        self.calls += 1
        if self.calls > self.fail_after:
            raise RuntimeError(
                "Error code: 402 - {'error': {'message': 'This request would exceed your "
                "available credits given your current in-flight requests'}}"
            )
        return _resp(content=json.dumps({
            "converged": True,
            "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0}],
            "line_flows": [{"line_id": 0, "p_from_mw": 156.9, "loading_percent": 60.0}],
            "total_generation_mw": 272.4,
            "total_load_mw": 259.0,
            "total_loss_mw": 13.4,
        }))


def _bench(client, **kw):
    params = dict(
        models=[FAKE_MODEL],
        methods=["llm_only:structured"],
        cases=["case14"],
        runs=1,
        temperature=0.0,
        timeout_s=10.0,
        pricing=PRICING,
        solver_config=SolverConfig(),
        client_factory=lambda spec: client,
        verbose=False,
        gen_requests=4,
    )
    params.update(kw)
    return run_benchmark(**params)


def test_the_run_stops_at_the_first_credit_error_instead_of_filling_the_rest():
    client = _DiesOnCredit(fail_after=1)
    with pytest.raises(ProviderOutage) as exc:
        _bench(client)
    # It says where it stopped, so the reader knows which rows exist.
    assert "completed rows" in str(exc.value)
    assert "available credits" in str(exc.value)
    # It stopped at the failure, it did not walk the remaining three items.
    assert client.calls == 2, client.calls


def test_a_run_with_no_outage_still_completes():
    """The guard must not fire on an ordinary run; otherwise it would be indistinguishable from
    a harness that simply refuses to work."""
    report = _bench(_DiesOnCredit(fail_after=99))
    assert report["runs"], "a clean run must still produce rows"


def test_the_aborted_run_leaves_a_marker_a_human_can_see(tmp_path, monkeypatch):
    """Without report.json the folder is invisible to the readers that walk `*/summary.json`.
    The marker is what stops an aborted run from looking like one nobody has scored yet."""
    import evaluation.runner as runner

    client = _DiesOnCredit(fail_after=0)
    monkeypatch.setattr(runner, "_default_client_factory", lambda spec: client)
    out = tmp_path / "run"
    code = runner.main([
        "--method", "llm_only:structured", "--case", "case14", "--model", "fake:scripted",
        "--gen-requests", "2", "--out-dir", str(out), "--pricing-file", "pricing.json",
        "--no-traces", "--quiet",
    ])
    assert code == 4, code
    assert not (out / "report.json").exists(), "an aborted run must not write a report"
    marker = out / "INCOMPLETO.txt"
    assert marker.exists(), "an aborted run must leave a visible marker"
    assert "ABORTED" in marker.read_text()
