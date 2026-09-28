"""Freeze the scenario set: ``data/scenarios/manifest.json``.

Every system the harness can run is frozen, not only the three a run covers by
default, so the page can show what IEEE-118 and IEEE-300 would pose and a
decision to add them costs nothing but the run.

One entry per (network, scenario): the content hash of the injected network,
its measured initial state, the injected fault and the base network's own
violations. ``run.py freeze-scenarios`` writes it; ``check(request)`` compares
a freshly built scenario with the manifest and raises when they differ, so a
pandapower release or a generator edit that changes the benchmark is caught on
load rather than discovered in a results table.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandapower as pp

from config import ALL_NETWORKS, NETWORKS, PROJECT_ROOT

MANIFEST = PROJECT_ROOT / "data" / "scenarios" / "manifest.json"


def entry_key(network: str, scenario_id: str, variant: int = 0) -> str:
    from evaluation.scenarios import instance_id

    return instance_id(network, scenario_id, variant)


def build_manifest(networks: Optional[List[str]] = None) -> Dict[str, Any]:
    from evaluation.requests import build_requests

    reqs = build_requests(list(networks or ALL_NETWORKS))
    entries = {}
    for r in reqs:
        entries[r.request_id] = {
            "network": r.network, "scenario_id": r.scenario_id, "variant": r.variant, "category": r.category,
            "network_hash": r.network_hash, "initial_state": r.initial.label,
            "initial_n_new_violations": r.initial.n_new, "initial_islanded_load_buses": r.initial.islanded_load_buses,
            "injected": r.injected.as_dict(), "base_violations": sorted(f"{k}:{i}" for k, i in r.base_keys),
        }
    return {
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pandapower": pp.__version__,
        "rating_rule": "line max_i_ka = 1.25 x base-case current, floor 5 % of the largest (solver/network.py)",
        "instances_per_network": __import__("evaluation.scenarios", fromlist=["N_INSTANCES"]).N_INSTANCES,
        "limits": {"v_min_pu": 0.95, "v_max_pu": 1.05, "max_loading_percent": 100.0},
        "entries": entries,
    }


def write_manifest(networks: Optional[List[str]] = None) -> Path:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(build_manifest(networks), indent=1), encoding="utf-8")
    return MANIFEST


def load_manifest() -> Optional[Dict[str, Any]]:
    return json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else None


def check(request: Any, manifest: Optional[Dict[str, Any]] = None) -> None:
    """Raise if the freshly built request differs from the frozen entry; silent when there is no manifest yet."""
    m = manifest if manifest is not None else load_manifest()
    if m is None:
        return
    e = m["entries"].get(request.request_id)
    if e is None:
        raise RuntimeError(f"{request.request_id} is not in data/scenarios/manifest.json; run `run.py freeze-scenarios` on purpose")
    if e["network_hash"] != request.network_hash:
        raise RuntimeError(
            f"{request.request_id}: injected network hash {request.network_hash} differs from the frozen {e['network_hash']} "
            f"(pandapower {pp.__version__}, frozen with {m.get('pandapower')}); the benchmark changed"
        )
    if e["initial_state"] != request.initial.label:
        raise RuntimeError(f"{request.request_id}: initial state {request.initial.label} differs from the frozen {e['initial_state']}")
