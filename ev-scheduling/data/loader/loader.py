"""Load sessions for one site-day: frozen local copy first, ACN-Data API second.

The 20 evaluation days behind paper §VI-B are committed under data/benchmark/ by
scripts/freeze_benchmark_days.py, so the benchmark reproduces with no token and no
network. The API is contacted only for a day that is not frozen yet and only when
ACN_DATA_API_TOKEN is set.

`source` (argument, or the EV_SESSIONS_SOURCE environment variable for callers that
do not pass it) selects where a day comes from:

  auto     frozen day file if present, else the API when a token is set (default)
  cache    frozen day file only; never touches the network
  api      API only; ignores the frozen copy (use to refresh a day)
  fixture  synthetic day from data/benchmark/fixtures/; never touches the network

Fixtures are generated, not measured. They exist so the pipeline can be exercised
offline. Every fixture load prints a warning to stderr and every fixture session ID
starts with SYNTH-, so a number computed from one is recognisable downstream.

The ev.caltech.edu API uses Eve and expects the "where" parameter as URL-encoded
MongoDB-style JSON (e.g. {"connectionTime": {"$gte": "RFC1123 date"}}). The acnportal
DataClient builds a non-JSON string that the API does not accept, so we build the
request and where clause here.
"""

import json
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from data.benchmark import store
from data.format.schema import DaySessions, Session

# Default max power (kW) when not provided by ACN-Data
DEFAULT_MAX_POWER_KW = 7.0
ACN_API_BASE = "https://ev.caltech.edu/api/v1/"

VALID_SITE_IDS = ("caltech", "jpl", "office001")

# Accepted values of the `source` argument (see module docstring).
SOURCE_AUTO = "auto"
SOURCE_CACHE = "cache"
SOURCE_API = "api"
SOURCE_FIXTURE = "fixture"
VALID_SOURCES = (SOURCE_AUTO, SOURCE_CACHE, SOURCE_API, SOURCE_FIXTURE)

# Environment override for callers that do not pass `source` (e.g. scripts/run_*.py).
SOURCE_ENV_VAR = "EV_SESSIONS_SOURCE"


def _rfc1123_utc(dt: datetime) -> str:
    """Format datetime as RFC 1123 in UTC (e.g. for Eve API)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def _parse_session_time(value: Any, day_start_utc: datetime) -> float:
    """Return seconds from day_start_utc. value may be RFC1123 str or datetime."""
    if value is None:
        return 0.0
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
    elif isinstance(value, str):
        # API returns RFC 1123; parse (e.g. "Wed, 07 Feb 2025 00:00:00 GMT")
        try:
            dt = datetime.strptime(value.strip(), "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
        except ValueError:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    else:
        return 0.0
    return (dt - day_start_utc).total_seconds()


def raw_session_to_standard(
    raw: Dict[str, Any],
    day_start_utc: datetime,
    dt_hours: float,
    n_steps: int,
) -> Session:
    """Map one raw ACN-Data session dict to Session.

    ACN-Data keys: connectionTime, disconnectTime, kWhDelivered, sessionID, spaceID.
    Converts times to step indices relative to day_start_utc (midnight UTC).
    """
    steps_per_hour = 1.0 / dt_hours
    conn_sec = _parse_session_time(raw.get("connectionTime"), day_start_utc)
    disc_sec = _parse_session_time(raw.get("disconnectTime"), day_start_utc)

    arrival_idx = int(round(conn_sec / 3600.0 * steps_per_hour))
    departure_idx = int(round(disc_sec / 3600.0 * steps_per_hour))
    arrival_idx = max(0, min(arrival_idx, n_steps - 1))
    departure_idx = max(arrival_idx + 1, min(departure_idx, n_steps))

    energy_kwh = float(raw.get("kWhDelivered", 0.0))
    if energy_kwh <= 0:
        energy_kwh = 1.0
    session_id = str(raw.get("sessionID", "")) or "unknown"
    charger_id = str(raw.get("spaceID", "")) or "unknown"
    max_power_kw = float(raw.get("maxPower", raw.get("max_power_kw", DEFAULT_MAX_POWER_KW)))
    if max_power_kw <= 0:
        max_power_kw = DEFAULT_MAX_POWER_KW

    return Session(
        session_id=session_id,
        arrival_idx=arrival_idx,
        departure_idx=departure_idx,
        energy_kwh=energy_kwh,
        charger_id=charger_id,
        max_power_kw=max_power_kw,
    )


def day_start_utc_for(day_date: date) -> datetime:
    """Return midnight UTC of the given calendar day (step 0 of the horizon)."""
    return datetime(day_date.year, day_date.month, day_date.day, 0, 0, 0, tzinfo=timezone.utc)


def records_to_day_sessions(
    records: List[Dict[str, Any]],
    day_date: date,
    n_steps: int = 96,
    dt_hours: float = 0.25,
) -> DaySessions:
    """Map a list of raw ACN-Data session dicts to DaySessions for the given horizon.

    Shared by the API path and the frozen-file path so both produce identical objects.
    """
    day_start = day_start_utc_for(day_date)
    sessions = [
        raw_session_to_standard(raw, day_start_utc=day_start, dt_hours=dt_hours, n_steps=n_steps)
        for raw in records
    ]
    return DaySessions(sessions=sessions, n_steps=n_steps, dt_hours=dt_hours)


def fetch_sessions_from_api(
    site_id: str,
    day_date: date,
    api_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch the raw session records for one site-day from the ACN-Data API.

    Uses an Eve-compatible where clause: MongoDB-style JSON with connectionTime
    $gte / $lte in RFC 1123, URL-encoded. Query window is midnight-to-midnight UTC
    for the given calendar day. Pagination via _links.next is followed.

    Args:
        site_id: One of 'caltech', 'jpl', 'office001'.
        day_date: Calendar day to fetch.
        api_token: ACN-Data token; falls back to ACN_DATA_API_TOKEN.

    Returns:
        The raw session dicts exactly as the API returned them, in API order.

    Raises:
        ValueError: If no API token is available, the site is unknown, or the API
            returns an error (401, 403, or an _error payload).
    """
    token = api_token
    if not (token and str(token).strip()):
        token = os.environ.get("ACN_DATA_API_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "ACN_DATA_API_TOKEN is required. Set it in .env or pass api_token to load_sessions."
        )
    if site_id not in VALID_SITE_IDS:
        raise ValueError("Invalid site. Must be 'caltech', 'jpl', or 'office001'.")

    # Midnight UTC for the requested day (inclusive start, exclusive end)
    day_start_utc = day_start_utc_for(day_date)
    day_end_utc = day_start_utc + timedelta(days=1)
    start_str = _rfc1123_utc(day_start_utc)
    end_str = _rfc1123_utc(day_end_utc)

    # Eve API expects where as URL-encoded JSON (MongoDB-style)
    where_json = {
        "$and": [
            {"connectionTime": {"$gte": start_str}},
            {"connectionTime": {"$lte": end_str}},
        ]
    }
    where_encoded = quote(json.dumps(where_json))
    url = f"{ACN_API_BASE}sessions/{site_id}?where={where_encoded}&sort=connectionTime&max_results=100"

    r = requests.get(url, auth=(token, ""), timeout=30)
    if r.status_code == 401:
        raise ValueError("ACN_DATA_API_TOKEN was rejected (401). Check your token at ev.caltech.edu.")
    if r.status_code == 403:
        raise ValueError("Access forbidden (403). Check your token and site access.")
    r.raise_for_status()

    payload = r.json()
    if "_error" in payload:
        raise ValueError(f"API error: {payload.get('_error', payload)}")

    items = payload.get("_items", [])
    records: List[Dict[str, Any]] = []

    # Paginate if there is a next link
    while True:
        records.extend(items)
        next_link = payload.get("_links", {}).get("next", {}).get("href")
        if not next_link:
            break
        # Next link may be relative or absolute
        next_url = next_link if next_link.startswith("http") else f"{ACN_API_BASE.rstrip('/')}{next_link}"
        r = requests.get(next_url, auth=(token, ""), timeout=30)
        r.raise_for_status()
        payload = r.json()
        items = payload.get("_items", [])

    return records


def load_frozen_day(
    site_id: str,
    day_date: date,
    synthetic: bool = False,
    benchmark_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Read one frozen day file (real or fixture) and return its validated document.

    Raises:
        FileNotFoundError: If the day is not frozen under benchmark_dir.
        ValueError: If the file is malformed, edited after freezing, or its synthetic
            flag does not match the folder it was read from.
    """
    path = store.day_path(site_id, day_date, synthetic=synthetic, benchmark_dir=benchmark_dir)
    payload = store.read_day_file(path)
    if bool(payload["synthetic"]) != synthetic:
        raise ValueError(
            f"{path} is marked synthetic={payload['synthetic']} but was read as "
            f"synthetic={synthetic}; refusing to mix measured and generated data."
        )
    if payload["site_id"] != site_id or payload["date"] != day_date.isoformat():
        raise ValueError(
            f"{path} holds {payload['site_id']} {payload['date']}, "
            f"not {site_id} {day_date.isoformat()}"
        )
    return payload


def _resolve_source(source: Optional[str]) -> str:
    """Return the effective source: explicit argument, else env var, else 'auto'."""
    value = source if source is not None else os.environ.get(SOURCE_ENV_VAR, "").strip()
    value = (value or SOURCE_AUTO).lower()
    if value not in VALID_SOURCES:
        raise ValueError(
            f"Invalid source {value!r}. Must be one of {', '.join(VALID_SOURCES)} "
            f"(set explicitly or via {SOURCE_ENV_VAR})."
        )
    return value


def load_sessions(
    site_id: str,
    day_date: date,
    api_token: Optional[str] = None,
    n_steps: int = 96,
    dt_hours: float = 0.25,
    source: Optional[str] = None,
    benchmark_dir: Optional[Path] = None,
) -> DaySessions:
    """Load sessions for the given site and date. Map to DaySessions.

    Prefers the frozen copy committed under data/benchmark/, so the paper's 20
    benchmark days load with no token and no network. Falls back to the ACN-Data API
    only when the day is not frozen and a token is available. See the module docstring
    for the meaning of each `source` value.

    Args:
        site_id: One of 'caltech', 'jpl', 'office001'.
        day_date: Calendar day to load (midnight-to-midnight UTC).
        api_token: ACN-Data token; falls back to ACN_DATA_API_TOKEN. Unused unless
            the API is actually contacted.
        n_steps: Horizon length in steps (96 = 24h at 15-minute resolution).
        dt_hours: Step duration in hours.
        source: 'auto' (default), 'cache', 'api', or 'fixture'. When None, the
            EV_SESSIONS_SOURCE environment variable is used, else 'auto'.
        benchmark_dir: Root of the frozen-day store. Defaults to data/benchmark/.

    Returns:
        DaySessions for the requested horizon.

    Raises:
        ValueError: If the site or source is invalid, the day is neither frozen nor
            reachable (no token), or the API returns an error.
        FileNotFoundError: If a 'cache' or 'fixture' load finds no frozen day file.
    """
    if site_id not in VALID_SITE_IDS:
        raise ValueError("Invalid site. Must be 'caltech', 'jpl', or 'office001'.")
    effective_source = _resolve_source(source)

    if effective_source == SOURCE_FIXTURE:
        payload = load_frozen_day(site_id, day_date, synthetic=True, benchmark_dir=benchmark_dir)
        print(
            f"WARNING: loading SYNTHETIC fixture sessions for {site_id} {day_date.isoformat()} "
            f"({payload['record_count']} generated sessions). Not measured data; "
            "results from this day must never be reported.",
            file=sys.stderr,
        )
        return records_to_day_sessions(payload["records"], day_date, n_steps, dt_hours)

    if effective_source in (SOURCE_AUTO, SOURCE_CACHE):
        try:
            payload = load_frozen_day(site_id, day_date, synthetic=False, benchmark_dir=benchmark_dir)
        except FileNotFoundError:
            if effective_source == SOURCE_CACHE:
                raise
            payload = None
        if payload is not None:
            return records_to_day_sessions(payload["records"], day_date, n_steps, dt_hours)

    # SOURCE_API, or SOURCE_AUTO with no frozen copy: go to the network.
    token = api_token or os.environ.get("ACN_DATA_API_TOKEN", "").strip()
    if not (token and str(token).strip()):
        raise ValueError(
            f"No frozen day file for {site_id} {day_date.isoformat()} at "
            f"{store.day_path(site_id, day_date, benchmark_dir=benchmark_dir)} and "
            "ACN_DATA_API_TOKEN is not set. Freeze the benchmark days with "
            "'python -m scripts.freeze_benchmark_days' once you have a token, or set "
            f"{SOURCE_ENV_VAR}=fixture to run the pipeline on synthetic days."
        )
    records = fetch_sessions_from_api(site_id, day_date, api_token=token)
    return records_to_day_sessions(records, day_date, n_steps, dt_hours)
