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
