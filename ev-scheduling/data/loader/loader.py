"""Load sessions from ACN-Data API; map to standardized format.

Requires ACN_DATA_API_TOKEN in .env or passed to load_sessions.

The ev.caltech.edu API uses Eve and expects the "where" parameter as URL-encoded
MongoDB-style JSON (e.g. {"connectionTime": {"$gte": "RFC1123 date"}}). The acnportal
DataClient builds a non-JSON string that the API does not accept, so we build the
request and where clause here.
"""

import json
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from data.format.schema import DaySessions, Session

# Default max power (kW) when not provided by ACN-Data
DEFAULT_MAX_POWER_KW = 7.0
ACN_API_BASE = "https://ev.caltech.edu/api/v1/"


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


def load_sessions(
    site_id: str,
    day_date: date,
    api_token: Optional[str] = None,
    n_steps: int = 96,
    dt_hours: float = 0.25,
) -> DaySessions:
    """Load sessions for the given site and date. Map to DaySessions.

    Uses Eve-compatible where clause: MongoDB-style JSON with connectionTime
    $gte / $lte in RFC 1123, URL-encoded. Query window is midnight-to-midnight UTC
    for the given calendar day.

    Raises:
        ValueError: If no API token is available or API returns an error.
    """
    token = api_token
    if not (token and str(token).strip()):
        token = os.environ.get("ACN_DATA_API_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "ACN_DATA_API_TOKEN is required. Set it in .env or pass api_token to load_sessions."
        )

    if site_id not in ("caltech", "jpl", "office001"):
        raise ValueError("Invalid site. Must be 'caltech', 'jpl', or 'office001'.")

    # Midnight UTC for the requested day (inclusive start, exclusive end)
    day_start_utc = datetime(day_date.year, day_date.month, day_date.day, 0, 0, 0, tzinfo=timezone.utc)
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
    sessions_list: List[Session] = []

    # Paginate if there is a next link
    while True:
        for raw in items:
            sessions_list.append(
                raw_session_to_standard(
                    raw,
                    day_start_utc=day_start_utc,
                    dt_hours=dt_hours,
                    n_steps=n_steps,
                )
            )
        next_link = payload.get("_links", {}).get("next", {}).get("href")
        if not next_link:
            break
        # Next link may be relative or absolute
        next_url = next_link if next_link.startswith("http") else f"{ACN_API_BASE.rstrip('/')}{next_link}"
        r = requests.get(next_url, auth=(token, ""), timeout=30)
        r.raise_for_status()
        payload = r.json()
        items = payload.get("_items", [])

    return DaySessions(sessions=sessions_list, n_steps=n_steps, dt_hours=dt_hours)
