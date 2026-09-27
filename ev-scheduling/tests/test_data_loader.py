"""Tests for the data loader: frozen benchmark days, synthetic fixtures, and the API path.

Everything here runs offline with no ACN_DATA_API_TOKEN and no network. The one test
that talks to the API skips itself when the token is not set.
"""

import ast
import importlib
import json
import os
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from data.benchmark import store
from data.format.schema import DaySessions, Session
from data.loader import loader
from data.loader.loader import load_sessions, raw_session_to_standard

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _no_network(*args: Any, **kwargs: Any) -> None:
    """Stand-in for requests.get that fails if any test reaches the network."""
    raise AssertionError("this test must not contact the network")


@pytest.fixture
def sample_day_sessions() -> DaySessions:
    """Hand-built DaySessions for tests that need data without calling the API."""
    sessions = [
        Session(
            "s1",
            arrival_idx=0,
            departure_idx=4,
            energy_kwh=10.0,
            charger_id="c1",
            max_power_kw=7.0,
        ),
        Session(
            "s2",
            arrival_idx=2,
            departure_idx=6,
            energy_kwh=5.0,
            charger_id="c2",
            max_power_kw=7.0,
        ),
    ]
    return DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)


def test_raw_session_to_standard() -> None:
    """raw_session_to_standard maps ACN-Data keys to Session with correct step indices."""
    day_start = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    # 8:00 UTC = 8h from midnight UTC -> step 8*4 = 32 at 15-min resolution
    # 12:00 UTC = step 48
    raw = {
        "sessionID": "test-123",
        "spaceID": "PS-001",
        "connectionTime": "Mon, 15 Jan 2024 08:00:00 GMT",
        "disconnectTime": "Mon, 15 Jan 2024 12:00:00 GMT",
        "kWhDelivered": 14.5,
    }
    s = raw_session_to_standard(raw, day_start_utc=day_start, dt_hours=0.25, n_steps=96)
    assert s.session_id == "test-123"
    assert s.charger_id == "PS-001"
    assert s.energy_kwh == 14.5
    assert 30 <= s.arrival_idx <= 34
    assert 46 <= s.departure_idx <= 50
    assert s.arrival_idx < s.departure_idx
    assert s.max_power_kw > 0


def test_load_sessions_with_api_returns_day_sessions() -> None:
    """When ACN_DATA_API_TOKEN is set, load_sessions returns DaySessions from the API."""
    if not os.environ.get("ACN_DATA_API_TOKEN", "").strip():
        pytest.skip("ACN_DATA_API_TOKEN not set; load .env or set token to run API test")
    day = load_sessions(
        site_id="caltech",
        day_date=date(2019, 5, 1),
        n_steps=96,
        dt_hours=0.25,
    )
    assert isinstance(day, DaySessions)
    assert day.n_steps == 96
    assert day.dt_hours == 0.25
    for s in day.sessions:
        assert 0 <= s.arrival_idx < s.departure_idx <= day.n_steps
        assert s.energy_kwh > 0
        assert s.max_power_kw > 0


# --- Frozen benchmark days and synthetic fixtures ---------------------------------


def _fixture_dates() -> List[date]:
    """Dates covered by the committed fixture manifest."""
    manifest = store.read_manifest(store.FIXTURES_DIR / store.MANIFEST_NAME)
    return [date.fromisoformat(row["date"]) for row in manifest["days"]]


def _benchmark_constants_from_runner() -> Tuple[str, List[date]]:
    """Read SITE_ID and BENCHMARK_DATES out of scripts/run_agent_vs_baseline.py.

    Parsed with ast rather than imported, so the test needs neither openai nor cvxpy.
    """
    source = (PROJECT_ROOT / "scripts" / "run_agent_vs_baseline.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    site_id = ""
    dates: List[date] = []
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = node.targets
        else:
            continue
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if "SITE_ID" in names:
            site_id = ast.literal_eval(node.value)
        if "BENCHMARK_DATES" in names:
            for element in node.value.elts:
                y, m, d = (ast.literal_eval(a) for a in element.args)
                dates.append(date(y, m, d))
    return site_id, dates


def test_benchmark_constants_match_the_runner() -> None:
    """store.BENCHMARK_DATES/SITE_ID mirror the ones the paper's runner uses."""
    site_id, dates = _benchmark_constants_from_runner()
    assert site_id == store.BENCHMARK_SITE_ID
    assert dates == store.BENCHMARK_DATES
    assert len(dates) == 20


def test_every_benchmark_date_has_a_fixture() -> None:
    """One synthetic stand-in exists for each benchmark date."""
    assert sorted(_fixture_dates()) == sorted(store.BENCHMARK_DATES)


def test_fixtures_are_unmistakably_synthetic() -> None:
    """Fixture files are labelled synthetic in the name, the document, and every record."""
    for day_date in _fixture_dates():
        path = store.day_path("caltech", day_date, synthetic=True)
        assert path.name.startswith(store.SYNTHETIC_PREFIX)
        payload = store.read_day_file(path)
        assert payload["synthetic"] is True
        assert payload["data_source"] == store.SOURCE_SYNTHETIC
        assert "SYNTHETIC" in payload["warning"]
        for record in payload["records"]:
            assert record["sessionID"].startswith("SYNTH-")
            assert record["spaceID"].startswith("SYNTH-")
            assert record["synthetic"] is True


def test_fixture_content_hashes_match_the_manifest() -> None:
    """Each fixture hashes to the value recorded in its file and in the manifest."""
    manifest = store.read_manifest(store.FIXTURES_DIR / store.MANIFEST_NAME)
    for row in manifest["days"]:
        payload = store.read_day_file(store.FIXTURES_DIR / row["file"])
        assert store.content_hash(payload["records"]) == payload["content_hash"]
        assert row["content_hash"] == payload["content_hash"]
        assert row["record_count"] == len(payload["records"])


def test_fixture_days_have_between_5_and_40_sessions() -> None:
    """Fixture day sizes stay in the range the benchmark pipeline is meant to handle."""
    for day_date in _fixture_dates():
        day = load_sessions("caltech", day_date, source="fixture")
        assert 5 <= len(day.sessions) <= 40
        for s in day.sessions:
            assert 0 <= s.arrival_idx < s.departure_idx <= day.n_steps
            assert s.energy_kwh > 0
            assert s.max_power_kw > 0


def test_at_least_three_fixture_days_are_congested() -> None:
    """Days flagged congested request more energy than the 50 kW cap can deliver."""
    congested = 0
    for day_date in _fixture_dates():
        payload = store.read_day_file(store.day_path("caltech", day_date, synthetic=True))
        day = load_sessions("caltech", day_date, source="fixture")
        requested = sum(s.energy_kwh for s in day.sessions)
        bound = store.deliverable_upper_bound_kwh(day.sessions, 50.0, day.n_steps, day.dt_hours)
        # The label and the arithmetic must agree: a congested day cannot be fully served.
        assert payload["congested"] == (requested > bound)
        congested += int(payload["congested"])
    assert congested >= 3


def test_load_sessions_fixture_needs_no_token_and_no_network(monkeypatch) -> None:
    """A fixture load works with the token unset and the network unavailable."""
    monkeypatch.delenv("ACN_DATA_API_TOKEN", raising=False)
    monkeypatch.setattr(loader.requests, "get", _no_network)
    day = load_sessions("caltech", store.BENCHMARK_DATES[0], source="fixture")
    assert isinstance(day, DaySessions)
    assert len(day.sessions) > 0
    assert all(s.session_id.startswith("SYNTH-") for s in day.sessions)


def test_env_var_selects_the_fixture_source(monkeypatch) -> None:
    """EV_SESSIONS_SOURCE switches callers that do not pass source themselves."""
    monkeypatch.delenv("ACN_DATA_API_TOKEN", raising=False)
    monkeypatch.setattr(loader.requests, "get", _no_network)
    monkeypatch.setenv(loader.SOURCE_ENV_VAR, "fixture")
    day = load_sessions("caltech", store.BENCHMARK_DATES[1])
    assert len(day.sessions) > 0
    assert all(s.session_id.startswith("SYNTH-") for s in day.sessions)


def test_frozen_day_is_preferred_over_the_api(monkeypatch, tmp_path) -> None:
    """With a frozen file present, load_sessions never contacts the API even with a token."""
    day_date = date(2019, 5, 1)
    payload = store.build_day_file(
        site_id="caltech",
        day_date=day_date,
        records=[
            {
                "sessionID": "frozen-1",
                "spaceID": "PS-007",
                "connectionTime": "Wed, 01 May 2019 08:00:00 GMT",
                "disconnectTime": "Wed, 01 May 2019 16:00:00 GMT",
                "kWhDelivered": 18.0,
                "maxPower": 6.6,
            }
        ],
        data_source=store.SOURCE_ACN_API,
        synthetic=False,
    )
    store.write_day_file(tmp_path / store.day_filename("caltech", day_date), payload)

    monkeypatch.setenv("ACN_DATA_API_TOKEN", "would-work-but-must-not-be-used")
    monkeypatch.setattr(loader.requests, "get", _no_network)
    day = load_sessions("caltech", day_date, benchmark_dir=tmp_path)
    assert [s.session_id for s in day.sessions] == ["frozen-1"]
    assert day.sessions[0].energy_kwh == 18.0
    assert day.sessions[0].max_power_kw == 6.6


def test_write_day_file_refuses_to_overwrite(tmp_path) -> None:
    """A frozen day is never clobbered unless force is passed."""
    day_date = date(2019, 5, 1)
    payload = store.build_day_file(
        site_id="caltech",
        day_date=day_date,
        records=[],
        data_source=store.SOURCE_ACN_API,
        synthetic=False,
    )
    path = tmp_path / store.day_filename("caltech", day_date)
    store.write_day_file(path, payload)
    with pytest.raises(FileExistsError):
        store.write_day_file(path, payload)
    store.write_day_file(path, payload, force=True)


def test_freeze_script_keeps_existing_days_without_force(monkeypatch, tmp_path) -> None:
    """freeze_benchmark_days re-fetches nothing that is already frozen, and writes a manifest."""
    freeze = importlib.import_module("scripts.freeze_benchmark_days")
    day_date = date(2019, 5, 1)
    calls: List[date] = []

    def fake_fetch(site_id: str, fetch_date: date, api_token=None) -> List[Dict[str, object]]:
        calls.append(fetch_date)
        return [
            {
                "sessionID": f"api-{fetch_date.isoformat()}",
                "spaceID": "PS-001",
                "connectionTime": "Wed, 01 May 2019 09:00:00 GMT",
                "disconnectTime": "Wed, 01 May 2019 17:00:00 GMT",
                "kWhDelivered": 11.0,
            }
        ]

    monkeypatch.setattr(freeze, "fetch_sessions_from_api", fake_fetch)

    assert freeze.freeze_days("caltech", [day_date], tmp_path, api_token="t") == 0
    assert calls == [day_date]
    assert freeze.freeze_days("caltech", [day_date], tmp_path, api_token="t") == 0
    assert calls == [day_date]  # second run kept the file instead of re-fetching
    assert freeze.freeze_days("caltech", [day_date], tmp_path, api_token="t", force=True) == 0
    assert calls == [day_date, day_date]

    manifest = store.read_manifest(tmp_path / store.MANIFEST_NAME)
    assert manifest["site_id"] == "caltech"
    assert manifest["synthetic"] is False
    assert [row["date"] for row in manifest["days"]] == [day_date.isoformat()]
    assert manifest["days"][0]["record_count"] == 1
    assert manifest["days"][0]["content_hash"].startswith("sha256:")

    # The frozen day now loads offline, with no token and no network.
    monkeypatch.delenv("ACN_DATA_API_TOKEN", raising=False)
    monkeypatch.setattr(loader.requests, "get", _no_network)
    day = load_sessions("caltech", day_date, source="cache", benchmark_dir=tmp_path)
    assert [s.session_id for s in day.sessions] == [f"api-{day_date.isoformat()}"]


def test_missing_day_without_token_explains_how_to_fix_it(monkeypatch, tmp_path) -> None:
    """The error names the freeze script and the fixture switch instead of just failing."""
    monkeypatch.delenv("ACN_DATA_API_TOKEN", raising=False)
    monkeypatch.setattr(loader.requests, "get", _no_network)
    with pytest.raises(ValueError) as exc:
        load_sessions("caltech", date(2019, 5, 1), benchmark_dir=tmp_path)
    message = str(exc.value)
    assert "freeze_benchmark_days" in message
    assert loader.SOURCE_ENV_VAR in message


def test_cache_source_never_falls_back_to_the_network(monkeypatch, tmp_path) -> None:
    """source='cache' raises on a missing day even when a token is available."""
    monkeypatch.setenv("ACN_DATA_API_TOKEN", "unused")
    monkeypatch.setattr(loader.requests, "get", _no_network)
    with pytest.raises(FileNotFoundError):
        load_sessions("caltech", date(2019, 5, 1), source="cache", benchmark_dir=tmp_path)


def test_invalid_source_is_rejected() -> None:
    """An unknown source value fails loudly rather than silently going to the API."""
    with pytest.raises(ValueError, match="Invalid source"):
        load_sessions("caltech", date(2019, 5, 1), source="whatever")


def test_edited_day_file_is_rejected(tmp_path) -> None:
    """A day file edited after freezing fails its content hash."""
    day_date = date(2019, 5, 1)
    payload = store.build_day_file(
        site_id="caltech",
        day_date=day_date,
        records=[
            {
                "sessionID": "frozen-1",
                "spaceID": "PS-007",
                "connectionTime": "Wed, 01 May 2019 08:00:00 GMT",
                "disconnectTime": "Wed, 01 May 2019 16:00:00 GMT",
                "kWhDelivered": 18.0,
            }
        ],
        data_source=store.SOURCE_ACN_API,
        synthetic=False,
    )
    path = tmp_path / store.day_filename("caltech", day_date)
    store.write_day_file(path, payload)

    edited = json.loads(path.read_text(encoding="utf-8"))
    edited["records"][0]["kWhDelivered"] = 180.0
    path.write_text(json.dumps(edited), encoding="utf-8")

    with pytest.raises(ValueError, match="content_hash mismatch"):
        load_sessions("caltech", day_date, source="cache", benchmark_dir=tmp_path)


def test_synthetic_file_cannot_pose_as_a_real_day(tmp_path) -> None:
    """A fixture dropped into the real-day folder is refused, not silently loaded."""
    day_date = date(2019, 5, 1)
    fixture = store.read_day_file(store.day_path("caltech", day_date, synthetic=True))
    path = tmp_path / store.day_filename("caltech", day_date)
    store.write_day_file(path, fixture)
    with pytest.raises(ValueError, match="synthetic"):
        load_sessions("caltech", day_date, source="cache", benchmark_dir=tmp_path)
