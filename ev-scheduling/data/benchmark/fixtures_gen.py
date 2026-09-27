"""Generate the synthetic fixture days under data/benchmark/fixtures/.

These days are NOT measurements. They exist so the optimizer, constraint checker,
baseline, agent, and evaluation code can be exercised offline, before or without an
ACN-Data token. Every generated record is labelled synthetic three times over: the
file name starts with SYNTHETIC_, the document carries synthetic: true plus a warning
string, and every sessionID and spaceID starts with SYNTH-.

One fixture stands in for each of the 20 benchmark dates, so a run pointed at fixtures
(EV_SESSIONS_SOURCE=fixture) exercises the same 20-day loop as the real benchmark.

Generation is deterministic: the seed of a day is its date as YYYYMMDD, so rerunning
this module reproduces the committed files byte for byte.

Usage (from the project root):
    python -m data.benchmark.fixtures_gen            # write missing fixtures
    python -m data.benchmark.fixtures_gen --force    # regenerate all of them
"""

import argparse
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from data.benchmark import store
from data.format.schema import Session

# Horizon the fixtures are laid out on. Files store clock times, so a caller may still
# load them at another resolution; these are only the grid the generator draws on.
N_STEPS = 96
DT_HOURS = 0.25

# Site power cap used to decide whether a generated day is congested (kW). Matches
# P_MAX_KW in scripts/run_agent_vs_baseline.py.
SITE_CAP_KW = 50.0

# Level-2 EVSE power ratings (kW) and their relative frequency at the site.
POWER_RATINGS_KW: List[Tuple[float, float]] = [(3.3, 0.15), (6.6, 0.45), (7.0, 0.25), (7.2, 0.15)]

GENERATOR = "data/benchmark/fixtures_gen.py"


@dataclass(frozen=True)
class DayProfile:
    """Shape of one generated day.

    Attributes:
        name: Short profile label stored in the file and the manifest.
        n_sessions: Number of sessions to generate (5 to 40).
        morning_arrival: (mean, sd) arrival hour of the commuter peak.
        afternoon_share: Fraction of sessions that arrive in the afternoon instead.
        dwell: (mean, sd) dwell time in hours.
        energy_fill: (low, high) requested energy as a fraction of what the session's
            own power limit could deliver over its dwell window, before rescaling.
        demand_ratio: (low, high) target for the whole day's requested energy divided
            by the energy the 50 kW cap could deliver. Below 1 the day is servable in
            full; above 1 it must end with unmet energy.
        congested: True when the day is built so that demand exceeds what the 50 kW
            site cap can deliver, i.e. the day must end with unmet energy.
        notes: One line saying what makes this day distinctive.
    """

    name: str
    n_sessions: int
    morning_arrival: Tuple[float, float]
    afternoon_share: float
    dwell: Tuple[float, float]
    energy_fill: Tuple[float, float]
    demand_ratio: Tuple[float, float]
    congested: bool
    notes: str


# One profile per benchmark date, in the order of store.BENCHMARK_DATES.
DAY_PROFILES: List[DayProfile] = [
    DayProfile("congested_peak", 38, (8.0, 1.0), 0.10, (7.5, 1.5), (0.80, 0.95), (2.30, 2.60), True,
               "38 sessions, tight morning peak, near-full requests; demand far above the 50 kW cap"),
    DayProfile("typical_weekday", 24, (8.5, 1.4), 0.20, (7.0, 2.0), (0.45, 0.75), (0.62, 0.80), False,
               "24 sessions, ordinary commuter shape with slack under the cap"),
    DayProfile("light_day", 9, (9.0, 2.0), 0.30, (5.5, 2.0), (0.40, 0.70), (0.45, 0.65), False,
               "9 sessions spread over the day, large headroom"),
    DayProfile("typical_weekday", 21, (8.2, 1.2), 0.15, (8.0, 2.5), (0.50, 0.80), (0.60, 0.78), False,
               "21 sessions with long dwell times, easily feasible"),
    DayProfile("congested_short_dwell", 34, (8.3, 0.8), 0.05, (4.0, 1.0), (0.85, 0.98), (2.10, 2.35), True,
               "34 sessions with short 4 h windows and near-full requests; worst unmet-energy day"),
    DayProfile("typical_weekday", 19, (8.8, 1.6), 0.25, (6.5, 2.0), (0.45, 0.75), (0.60, 0.80), False,
               "19 sessions, mixed morning and afternoon arrivals"),
    DayProfile("long_dwell", 16, (7.5, 1.0), 0.10, (10.0, 2.0), (0.35, 0.60), (0.45, 0.62), False,
               "16 sessions parked all day; wide scheduling freedom for the optimizer"),
    DayProfile("congested_midday", 36, (9.5, 1.5), 0.35, (6.0, 1.5), (0.80, 0.95), (1.55, 1.75), True,
               "36 sessions with heavy midday overlap; congestion centred on the peak TOU window"),
    DayProfile("minimum_day", 5, (9.5, 2.5), 0.40, (6.0, 2.5), (0.40, 0.80), (0.45, 0.70), False,
               "smallest day, 5 sessions; exercises the small-input path of the baseline prompt"),
    DayProfile("typical_weekday", 27, (8.4, 1.3), 0.20, (7.0, 2.0), (0.50, 0.80), (0.65, 0.82), False,
               "27 sessions, standard shape"),
    DayProfile("typical_weekday", 22, (8.6, 1.5), 0.20, (6.8, 2.0), (0.45, 0.75), (0.60, 0.80), False,
               "22 sessions, standard shape, autumn schedule"),
    DayProfile("tight_but_feasible", 30, (8.1, 1.1), 0.10, (8.5, 2.0), (0.55, 0.75), (0.90, 0.95), False,
               "30 sessions whose demand sits just under the cap; feasible only if load is spread"),
    DayProfile("light_day", 11, (9.2, 2.2), 0.35, (5.0, 2.0), (0.40, 0.70), (0.45, 0.65), False,
               "11 sessions, short visits, large headroom"),
    DayProfile("typical_weekday", 25, (8.5, 1.4), 0.20, (7.2, 2.2), (0.50, 0.78), (0.62, 0.80), False,
               "25 sessions, standard shape"),
    DayProfile("overnight_tail", 18, (16.0, 2.5), 0.00, (9.0, 2.5), (0.45, 0.75), (0.60, 0.78), False,
               "18 evening arrivals, several sessions still plugged in at the end of the horizon"),
    DayProfile("typical_weekday", 23, (8.3, 1.3), 0.20, (7.0, 2.0), (0.48, 0.76), (0.60, 0.80), False,
               "23 sessions, standard shape"),
    DayProfile("congested_all_day", 40, (8.6, 2.2), 0.30, (7.0, 2.0), (0.75, 0.95), (1.55, 1.75), True,
               "largest day, 40 sessions arriving all day; the cap binds from morning to evening"),
    DayProfile("light_day", 8, (10.0, 2.5), 0.40, (4.5, 1.5), (0.40, 0.75), (0.45, 0.68), False,
               "8 short visits; several sessions cannot overlap at all"),
    DayProfile("typical_weekday", 20, (8.7, 1.5), 0.25, (6.5, 2.0), (0.45, 0.75), (0.60, 0.80), False,
               "20 sessions, standard shape"),
    DayProfile("few_large_requests", 7, (7.8, 1.0), 0.10, (9.5, 1.5), (0.85, 0.98), (0.85, 0.93), False,
               "7 sessions but each asks for nearly everything its charger can deliver"),
]


def _weighted_choice(rng: random.Random, options: List[Tuple[float, float]]) -> float:
    """Pick one value from (value, weight) pairs using rng."""
    total = sum(w for _, w in options)
    draw = rng.uniform(0.0, total)
    upto = 0.0
    for value, weight in options:
        upto += weight
        if draw <= upto:
            return value
    return options[-1][0]


def _clip(value: float, low: float, high: float) -> float:
    """Clamp value into [low, high]."""
    return max(low, min(high, value))


def _rfc1123(day_date: date, step_idx: float) -> str:
    """Render a step offset from midnight UTC as an RFC 1123 timestamp."""
    dt = datetime(day_date.year, day_date.month, day_date.day, tzinfo=timezone.utc)
    dt = dt + timedelta(hours=step_idx * DT_HOURS)
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def _make_records(profile: DayProfile, day_date: date, seed: int) -> List[Dict[str, Any]]:
    """Generate the raw ACN-style records for one fixture day.

    Arrival and departure windows overlap the way a workplace site's do: a morning
    commuter peak, a smaller afternoon wave, and dwell times from under an hour to
    the rest of the day. Requested energy is a fraction of what the session's own
    charger could deliver while it is plugged in, so no request is impossible on its
    own; on congested days the aggregate is what the 50 kW site cap cannot serve.
    """
    rng = random.Random(seed)
    records: List[Dict[str, Any]] = []

    for i in range(profile.n_sessions):
        if rng.random() < profile.afternoon_share:
            arrival_h = rng.gauss(profile.morning_arrival[0] + 5.0, 1.8)
        else:
            arrival_h = rng.gauss(*profile.morning_arrival)
        arrival_h = _clip(arrival_h, 0.0, 22.5)

        dwell_h = _clip(rng.gauss(*profile.dwell), 0.75, 24.0 - arrival_h)

        arrival_idx = int(round(arrival_h / DT_HOURS))
        arrival_idx = max(0, min(arrival_idx, N_STEPS - 1))
        departure_idx = int(round((arrival_h + dwell_h) / DT_HOURS))
        departure_idx = max(arrival_idx + 1, min(departure_idx, N_STEPS))

        window_h = (departure_idx - arrival_idx) * DT_HOURS
        max_power_kw = _weighted_choice(rng, POWER_RATINGS_KW)
        fill = rng.uniform(*profile.energy_fill)
        energy_kwh = round(max(0.5, max_power_kw * window_h * fill), 2)

        records.append(
            {
                "sessionID": f"SYNTH-{day_date.isoformat()}-{i + 1:03d}",
                "spaceID": f"SYNTH-CA-{rng.randint(101, 154)}",
                "connectionTime": _rfc1123(day_date, arrival_idx),
                "disconnectTime": _rfc1123(day_date, departure_idx),
                "kWhDelivered": energy_kwh,
                "maxPower": max_power_kw,
                "synthetic": True,
            }
        )

    return records


def _records_to_sessions(records: List[Dict[str, Any]], day_date: date) -> List[Session]:
    """Map generated records to Session objects (same path the loader uses)."""
    from data.loader.loader import records_to_day_sessions

    return records_to_day_sessions(records, day_date, n_steps=N_STEPS, dt_hours=DT_HOURS).sessions


def _congestion(records: List[Dict[str, Any]], day_date: date) -> Tuple[float, float]:
    """Return (requested kWh, upper bound on deliverable kWh under the 50 kW cap)."""
    sessions = _records_to_sessions(records, day_date)
    requested = sum(s.energy_kwh for s in sessions)
    bound = store.deliverable_upper_bound_kwh(sessions, SITE_CAP_KW, N_STEPS, DT_HOURS)
    return requested, bound


def _scale_to_demand_ratio(
    records: List[Dict[str, Any]],
    day_date: date,
    target_ratio: float,
) -> None:
    """Rescale requested energy in place so the day's demand hits a chosen ratio.

    The ratio is requested energy over the deliverable upper bound under the 50 kW
    cap: below 1 the day is servable in full, above 1 it must end with unmet energy.
    Scaling keeps the relative shape drawn per session and never lets a request pass
    98 percent of what that session's own charger could deliver while plugged in, so
    no request is impossible on its own. Arrival and departure windows are untouched,
    so the bound itself does not move.
    """
    sessions = _records_to_sessions(records, day_date)
    requested = sum(s.energy_kwh for s in sessions)
    bound = store.deliverable_upper_bound_kwh(sessions, SITE_CAP_KW, N_STEPS, DT_HOURS)
    if requested <= 0:
        return
    scale = target_ratio * bound / requested

    for record, session in zip(records, sessions):
        window_h = (session.departure_idx - session.arrival_idx) * DT_HOURS
        ceiling = 0.98 * float(record["maxPower"]) * window_h
        record["kWhDelivered"] = round(_clip(session.energy_kwh * scale, 0.5, ceiling), 2)


def generate_day(profile: DayProfile, day_date: date) -> Dict[str, Any]:
    """Build the full fixture document for one day.

    Requested energy is rescaled to the profile's demand ratio and the result is
    checked: a congested profile must end above 1.1x the deliverable upper bound
    (so the day provably leaves unmet energy under any scheduler) and every other
    profile must end below 0.98x it. Seeds are retried until both hold.

    Raises:
        RuntimeError: If no seed in 50 attempts satisfies the profile.
    """
    base_seed = int(day_date.strftime("%Y%m%d"))
    for attempt in range(50):
        seed = base_seed + attempt
        records = _make_records(profile, day_date, seed)
        target = random.Random(seed + 7).uniform(*profile.demand_ratio)
        _scale_to_demand_ratio(records, day_date, target)
        requested, bound = _congestion(records, day_date)
        ratio = requested / bound if bound > 0 else 0.0
        if (profile.congested and ratio > 1.10) or (not profile.congested and ratio < 0.98):
            break
    else:
        raise RuntimeError(
            f"No seed in 50 attempts gave a {'congested' if profile.congested else 'feasible'} "
            f"day for {day_date} with profile {profile.name}"
        )

    extra = {
        "generator": GENERATOR,
        "seed": seed,
        "profile": profile.name,
        "congested": profile.congested,
        "demand_ratio": round(ratio, 3),
        "notes": profile.notes,
        "stands_in_for": {"site_id": store.BENCHMARK_SITE_ID, "date": day_date.isoformat()},
        "horizon": {"n_steps": N_STEPS, "dt_hours": DT_HOURS},
        "requested_energy_kwh": round(requested, 2),
        "deliverable_upper_bound_kwh": round(bound, 2),
        "site_cap_kw": SITE_CAP_KW,
    }
    return store.build_day_file(
        site_id=store.BENCHMARK_SITE_ID,
        day_date=day_date,
        records=records,
        data_source=store.SOURCE_SYNTHETIC,
        synthetic=True,
        fetched_at_utc=f"{day_date.isoformat()}T00:00:00Z",
        extra=extra,
    )


def generate_all(fixtures_dir: Path, force: bool = False) -> List[Path]:
    """Generate every fixture day and the fixtures manifest.

    Args:
        fixtures_dir: Destination folder (data/benchmark/fixtures/).
        force: Overwrite existing fixture files instead of keeping them.

    Returns:
        The paths written, in date order of the benchmark list.
    """
    if len(DAY_PROFILES) != len(store.BENCHMARK_DATES):
        raise ValueError(
            f"{len(DAY_PROFILES)} profiles for {len(store.BENCHMARK_DATES)} benchmark dates"
        )

    fixtures_dir = Path(fixtures_dir)
    written: List[Path] = []
    entries: List[Dict[str, Any]] = []

    for profile, day_date in zip(DAY_PROFILES, store.BENCHMARK_DATES):
        path = fixtures_dir / store.day_filename(store.BENCHMARK_SITE_ID, day_date, synthetic=True)
        if path.exists() and not force:
            print(f"keep   {path.name} (exists; --force to regenerate)")
            entries.append(store.build_manifest_entry(store.read_day_file(path), path))
            continue
        payload = generate_day(profile, day_date)
        store.write_day_file(path, payload, force=True)
        entries.append(store.build_manifest_entry(payload, path))
        written.append(path)
        print(
            f"write  {path.name}  {payload['record_count']:2d} sessions  "
            f"{payload['profile']}{'  CONGESTED' if payload['congested'] else ''}"
        )

    store.write_manifest(
        fixtures_dir / store.MANIFEST_NAME,
        site_id=store.BENCHMARK_SITE_ID,
        entries=entries,
        data_source=store.SOURCE_SYNTHETIC,
        synthetic=True,
        extra={
            "generator": GENERATOR,
            "site_cap_kw": SITE_CAP_KW,
            "horizon": {"n_steps": N_STEPS, "dt_hours": DT_HOURS},
            "purpose": (
                "Offline stand-ins for the 20 benchmark dates so the pipeline and tests run "
                "without an ACN-Data token. Load with source='fixture' or EV_SESSIONS_SOURCE=fixture."
            ),
        },
    )
    return written


def main() -> int:
    """CLI entry point: regenerate the committed fixture days."""
    parser = argparse.ArgumentParser(description="Generate synthetic EV session fixture days.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=store.FIXTURES_DIR,
        help="Destination folder (default: data/benchmark/fixtures)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing fixture files")
    args = parser.parse_args()

    written = generate_all(args.out_dir, force=args.force)
    print(f"\n{len(written)} fixture day(s) written to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
