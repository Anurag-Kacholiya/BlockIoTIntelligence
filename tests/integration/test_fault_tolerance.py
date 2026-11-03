"""Fault-tolerance add-on (ADR Experiment F): components that fail during a run. Faults that last the whole stream
make the outcome deterministic; the QBFT test crashes a validator part-way through. Needs the prepared data and
models (and Anvil / Besu for the blockchain tests)."""

import pytest

from src.common.blockchain import ANVIL
from src.common.config import load_config, resolve
from src.common.faults import Fault

VIEW = load_config("models")["training"]["view"]
READY = (resolve(load_config("datasets")["paths"]["splits"]) / VIEW / "test.parquet").exists() \
    and resolve("models/cloud/current.json").exists()

pytestmark = [pytest.mark.dataset, pytest.mark.skipif(not READY, reason="needs prepared data and models")]

ROWS, KW = 1500, {"devices": 10, "edges": 2, "fogs": 2, "batch_size": 100, "log": lambda *_: None}
PREDS = ("device_pred", "edge_pred", "fog_pred", "cloud_pred")


def _run(faults, policy="recover", **kw):
    from src.pipeline import run

    return run(experiment="test", n_rows=ROWS, faults=faults, fault_policy=policy, **KW, **kw)


def _predictions(r):
    return {row["event_id"]: tuple(row[p] for p in PREDS) for row in r["cloud_rows"]}


@pytest.fixture(scope="module")
def reference():
    r = _run([])                                        # the fault loop with nothing failing
    assert r["faults"]["messages"]["delivered"] == ROWS and r["faults"]["log"] == []
    return _predictions(r)


@pytest.mark.parametrize("target", ["edge-01", "fog-01", "cloud"])
def test_recovery_loses_nothing_and_changes_no_result(target, reference):
    r = _run([Fault(target, 0)])
    m = r["faults"]["messages"]
    assert m == {"generated": ROWS, "sent": ROWS, "delivered": ROWS, "duplicates": 0, "rejected": 0, "lost": 0}
    moved = {"edge-01": "rerouted_edge", "fog-01": "rerouted_fog", "cloud": "held_for_cloud"}[target]
    assert r["faults"]["counts"][moved] > 0
    assert _predictions(r) == reference                 # every message, every layer's prediction, unchanged


@pytest.mark.parametrize("target, where", [("edge-01", "lost_at_edge"), ("fog-01", "lost_at_fog"),
                                           ("cloud", "lost_at_cloud")])
def test_without_recovery_the_traffic_of_the_failed_component_is_lost(target, where):
    r = _run([Fault(target, 0)], policy="none")
    m, counts = r["faults"]["messages"], r["faults"]["counts"]
    assert m["lost"] == counts[where] > 0 and m["delivered"] + m["lost"] == ROWS


def test_a_device_that_is_off_sends_nothing_and_nothing_else_changes(reference):
    r = _run([Fault("device:device-0003", 0)])
    m = r["faults"]["messages"]
    off = r["faults"]["counts"]["unsent_device_off"]
    assert off > 0 and m["sent"] == ROWS - off and m["delivered"] == m["sent"] and m["lost"] == 0
    assert {k: v for k, v in reference.items() if k in _predictions(r)} == _predictions(r)


@pytest.mark.skipif(not ANVIL.exists(), reason="needs anvil")
@pytest.mark.parametrize("mode", ["per_event", "batch"])
def test_another_edge_verifies_a_failed_edges_devices_through_the_ledger(mode):
    r = _run([Fault("edge-00", 0)], blockchain=mode)
    m = r["faults"]["messages"]
    assert m["lost"] == 0 and m["rejected"] == 0 and m["delivered"] == ROWS
    assert r["faults"]["counts"]["rerouted_edge"] > 0
    assert all(v["failed"] == 0 for v in r["chain"].values())


def _besu_ready():
    from src.common.qbft import BESU

    return BESU.exists()


@pytest.mark.skipif(not _besu_ready(), reason="needs Besu (scripts/setup_besu.py)")
def test_a_crashed_validator_loses_nothing_and_rejoins():
    """Node 1 (edge-00 and the cloud) crashes mid-run: its clients fail over, resend what was unconfirmed, and the
    restarted node catches up; every node ends with the same chain."""
    from src.pipeline import run

    r = run(experiment="test", blockchain="batch", n_rows=ROWS, devices=10, edges=2, fogs=2, batch_size=100,
            chain_backend="qbft", audit_writes="background", faults=[Fault("node:1", 3, 12)], log=lambda *_: None)
    f = r["faults"]
    assert f["messages"] == {"generated": ROWS, "sent": ROWS, "delivered": ROWS, "duplicates": 0, "rejected": 0,
                             "lost": 0}
    assert [x["node"] for x in f["failovers"]] == [1]
    assert [e["action"] for e in f["log"]] == ["down", "up", "resynced"]
    assert all(v["failed"] == 0 for v in r["chain"].values())
    consensus = r["chain_network"]["consensus"]
    assert consensus["consistent"] and consensus["validators"] == 4 and min(consensus["peers"]) >= 3
