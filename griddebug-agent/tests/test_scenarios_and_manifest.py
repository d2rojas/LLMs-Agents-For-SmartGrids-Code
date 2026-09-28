"""The instance set is frozen: every instance matches data/scenarios/manifest.json, and every fault is measurable."""

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
@pytest.mark.parametrize("scenario_id,variant", S.INSTANCES)
def test_instance_matches_the_frozen_manifest(network, scenario_id, variant):
    req = build_request(network, scenario_id, variant)
    M.check(req, MANIFEST)  # raises on a hash or state mismatch


def test_twenty_instances_of_thirteen_classes_per_network():
    assert S.N_INSTANCES == 20
    assert len({sid for sid, _v in S.INSTANCES}) == len(S.SCENARIOS) == 13
    for n in NETWORKS:
        assert sum(1 for e in MANIFEST["entries"].values() if e["network"] == n) == 20


def test_the_mix_is_balanced_across_the_failure_modes():
    """1 control, then five, five, five and four: no failure mode is a single instance."""
    by_cat: dict[str, int] = {}
    for sid, _v in S.INSTANCES:
        by_cat[S.CATEGORY_OF[sid]] = by_cat.get(S.CATEGORY_OF[sid], 0) + 1
    assert by_cat == {"normal": 1, "nonconvergence": 5, "voltage": 5, "thermal": 5, "contingency": 4}


def test_every_fault_injects_a_measurable_symptom():
    """Only normal_operation may start secure; every other instance is not converged, islanded or violating."""
    for key, e in MANIFEST["entries"].items():
        if e["scenario_id"] == "normal_operation":
            assert e["initial_state"] == "secure", key
        else:
            assert e["initial_state"] != "secure", f"{key} injects nothing measurable"


def test_instances_of_one_class_are_different_networks():
    """A variant has to move the fault; two instances that hash the same are one instance."""
    for n in NETWORKS:
        seen: dict[str, str] = {}
        for sid, v in S.INSTANCES:
            e = MANIFEST["entries"][S.instance_id(n, sid, v)]
            h = e["network_hash"]
            assert h not in seen, f"{n}: {sid}-v{v} is the same network as {seen[h]}"
            seen[h] = f"{sid}-v{v}"


def test_every_class_that_varies_says_what_its_variant_moves():
    for sid, n in S.VARIANTS_OF.items():
        assert (sid in S.VARIES_BY) == (n > 1), sid


def test_injected_fault_types_are_in_the_contract():
    for e in MANIFEST["entries"].values():
        assert e["injected"]["fault_type"] in S.FAULT_TYPES
