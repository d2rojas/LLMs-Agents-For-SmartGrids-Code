"""The scenario set is frozen: every instance matches data/scenarios/manifest.json, and every fault is measurable."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import NETWORKS  # noqa: E402
from evaluation import scenarios as S  # noqa: E402
from evaluation.requests import build_request  # noqa: E402
from evaluation.scenarios import manifest as M  # noqa: E402

MANIFEST = M.load_manifest()
pytestmark = pytest.mark.skipif(MANIFEST is None, reason="no manifest frozen yet")


@pytest.mark.parametrize("network", NETWORKS)
@pytest.mark.parametrize("scenario_id", S.SCENARIO_IDS)
def test_instance_matches_the_frozen_manifest(network, scenario_id):
    req = build_request(network, scenario_id)
    M.check(req, MANIFEST)  # raises on a hash or state mismatch


def test_every_fault_injects_a_measurable_symptom():
    """Only normal_operation may start secure; every other instance is not converged, islanded or violating."""
    for key, e in MANIFEST["entries"].items():
        if e["scenario_id"] == "normal_operation":
            assert e["initial_state"] == "secure", key
        else:
            assert e["initial_state"] != "secure", f"{key} injects nothing measurable"


def test_thirteen_scenarios_per_network():
    for n in NETWORKS:
        assert sum(1 for e in MANIFEST["entries"].values() if e["network"] == n) == 13


def test_contingency_scenarios_differ_from_topology_redirection():
    for n in NETWORKS:
        hashes = {sid: MANIFEST["entries"][f"{n}-{sid}"]["network_hash"] for sid in ("topology_redirection", "line_contingency_overload", "trafo_contingency_voltage")}
        assert len(set(hashes.values())) == 3, (n, hashes)


def test_injected_fault_types_are_in_the_contract():
    for e in MANIFEST["entries"].values():
        assert e["injected"]["fault_type"] in S.FAULT_TYPES
