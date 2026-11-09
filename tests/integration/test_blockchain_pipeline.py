"""End-to-end with the ledger on (ADR §17.3): every event committed, verified, processed and recorded;
tampered events rejected. Needs Anvil (tools/foundry) plus the prepared data and trained models."""

import pytest

from src.common.blockchain import ANVIL
from src.common.config import load_config, resolve

VIEW = load_config("models")["training"]["view"]
READY = ANVIL.exists() and (resolve(load_config("datasets")["paths"]["splits"]) / VIEW / "test.parquet").exists() \
    and resolve("models/cloud/current.json").exists()

pytestmark = [pytest.mark.dataset, pytest.mark.skipif(not READY, reason="needs anvil, prepared data and models")]


def _tamper_every_tenth(batch):
    for i, e in enumerate(batch):
        if i % 10 == 0:
            key = next(k for k, v in e["values"].items() if isinstance(v, float))
            e["values"][key] += 1.0
    return batch


@pytest.mark.parametrize("mode", ["per_event", "batch"])
def test_every_event_is_committed_and_verified(mode):
    from src.pipeline import run

    r = run(experiment="test", blockchain=mode, n_rows=300, devices=4, edges=2, fogs=1, batch_size=100,
            log=lambda *_: None)
    assert r["events_processed"] == 300 and r["events_rejected"] == 0
    chain = r["chain"]
    assert chain["device_commit"]["failed"] == 0 and chain["edge_processed"]["failed"] == 0
    if mode == "per_event":
        assert chain["device_commit"]["tx_count"] == 300      # one on-chain commitment per event
    assert chain["model_verify"]["call_count"] == 4           # all four layer models verified on-chain


@pytest.mark.parametrize("mode", ["per_event", "batch"])
def test_tampered_events_are_rejected(mode):
    from src.pipeline import run

    r = run(experiment="test", blockchain=mode, n_rows=300, devices=4, edges=2, fogs=1, batch_size=100,
            interceptor=_tamper_every_tenth, log=lambda *_: None)
    assert r["events_rejected"] == 30
    assert set(reason for _, reason in r["rejected"]) == {"hash_mismatch"}


@pytest.mark.parametrize("mode", ["per_event", "batch"])
def test_locally_signed_with_background_audit_writes(mode):
    """Final task 2 client on Anvil: same results; every background write is confirmed before the run returns."""
    from src.pipeline import run

    r = run(experiment="test", blockchain=mode, n_rows=300, devices=4, edges=2, fogs=1, batch_size=100,
            signing="local", audit_writes="background", log=lambda *_: None)
    assert r["events_processed"] == 300 and r["events_rejected"] == 0
    assert r["chain_network"] == {"backend": "anvil", "nodes": 1, "signing": "local", "audit_writes": "background",
                                  "roles": {"device_gateway": 0, "edge-00": 0, "edge-01": 0, "fog-00": 0, "cloud": 0}}
    chain = r["chain"]
    assert chain["cloud_inference_record"]["tx_count"] == 3                # one per micro-batch, all confirmed
    assert all(v["failed"] == 0 for v in chain.values())


def _besu_ready():
    from src.common.qbft import BESU

    return BESU.exists()


@pytest.mark.skipif(not READY or not _besu_ready(), reason="needs Besu (scripts/setup_besu.py)")
@pytest.mark.parametrize("mode", ["per_event", "batch"])
def test_qbft_network_end_to_end(mode):
    """4 validators: every event committed through one node is verified through another; tampering still caught;
    all nodes agree on the chain."""
    from src.pipeline import run

    r = run(experiment="test", blockchain=mode, n_rows=300, devices=4, edges=2, fogs=1, batch_size=100,
            chain_backend="qbft", audit_writes="background", interceptor=_tamper_every_tenth, log=lambda *_: None)
    assert r["events_processed"] == 270 and r["events_rejected"] == 30
    assert set(reason for _, reason in r["rejected"]) == {"hash_mismatch"}
    net = r["chain_network"]
    assert net["backend"] == "qbft" and net["nodes"] == 4 and net["signing"] == "local"
    assert net["consensus"]["consistent"] and net["consensus"]["validators"] == 4
    assert all(p >= 3 for p in net["consensus"]["peers"])
    assert all(v["failed"] == 0 for v in r["chain"].values())
