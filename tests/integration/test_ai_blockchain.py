"""Final task 3 (RQ-11): the gateway's AI-driven commit scheduling of Merkle batches, end to end on dataset v2's
realistic replay. Needs the real_time data and models, the trained forecaster, and Anvil (Besu for the QBFT test)."""

import pytest

from src.common.blockchain import ANVIL
from src.common.config import load_config, resolve

SPLITS = resolve(load_config("datasets")["paths"]["splits"])
READY = ANVIL.exists() and (SPLITS / "real" / "session_cuts.parquet").exists() \
    and resolve("models/real_time/cloud/current.json").exists() \
    and resolve("models/real_time/device_forecaster/current.json").exists()

pytestmark = [pytest.mark.dataset,
              pytest.mark.skipif(not READY, reason="needs dataset v2, its models, the forecaster and anvil")]

ROWS, REPLICAS, BATCH = 1500, 10, 128          # 100 devices, 12 rounds
POLICY = {"policy": "forecast", "hold_rounds": 1, "break_even": 4}
PREDS = ("device_pred", "edge_pred", "fog_pred", "cloud_pred")


@pytest.fixture(autouse=True)
def real_time_view(monkeypatch):
    monkeypatch.setenv("BLOCKIOT_VIEW", "real_time")


def _run(policy=None, **kw):
    from src.pipeline import run

    kw = {"chain_backend": "anvil", "signing": "local", "audit_writes": "background"} | kw
    return run(experiment="test", blockchain="batch", n_rows=ROWS, replay="realistic", replicas=REPLICAS, edges=2,
               fogs=1, batch_size=BATCH, commit_policy=policy, log=lambda *_: None, **kw)


def _predictions(r):
    return {row["event_id"]: tuple(row[p] for p in PREDS) for row in r["cloud_rows"]}


def _offline_roots(policy):
    from src.device.commit_policy import TrafficForecaster, make_policy, simulate
    from src.device.simulator import RealtimeReplay
    from src.pipeline import load_replay_rows

    rows, _ = load_replay_rows(ROWS)
    sim = RealtimeReplay(rows, replicas=REPLICAS)
    return simulate(sim, make_policy(dict(policy), forecaster=TrafficForecaster()), BATCH)["roots"]


@pytest.fixture(scope="module")
def fixed():
    """The fixed design (one root per device per round) through the scheduler, so its cloud rows are returned."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("BLOCKIOT_VIEW", "real_time")
        return _run({"policy": "fixed"})


def test_the_fixed_policy_is_the_original_design(fixed):
    original = _run(None)                                      # no scheduler: the code path of every earlier task
    for kind in ("device_commit", "edge_processed"):
        assert fixed["chain"][kind]["tx_count"] == original["chain"][kind]["tx_count"]
        assert fixed["chain"][kind]["gas_total"] == original["chain"][kind]["gas_total"]
    assert fixed["accuracy"] == original["accuracy"] and fixed["commit_schedule"]["held_message_rounds"] == 0


def test_ai_scheduling_commits_fewer_roots_and_changes_no_result(fixed):
    r = _run(POLICY)
    assert r["events_processed"] == ROWS and r["events_rejected"] == 0
    assert all(v["failed"] == 0 for v in r["chain"].values())
    roots, fixed_roots = r["chain"]["device_commit"]["tx_count"], fixed["chain"]["device_commit"]["tx_count"]
    assert roots < fixed_roots and r["chain"]["edge_processed"]["tx_count"] == roots   # one processing record each
    assert r["commit_schedule"]["roots"] == roots == _offline_roots(POLICY)   # live decisions = offline simulation
    assert max(map(int, r["commit_schedule"]["held_roots_by_rounds"])) <= POLICY["hold_rounds"]
    assert r["chain"]["model_verify"]["call_count"] == 5      # the forecaster is registered and verified on-chain
    assert _predictions(r) == _predictions(fixed)             # every message, every layer's prediction, unchanged
    assert r["accuracy"] == fixed["accuracy"]
    assert r["message_latency_ms"]["all"]["count"] == ROWS


def test_a_tampered_message_from_a_held_batch_is_rejected():
    tampered = []

    def tamper(batch):
        for i, e in enumerate(batch):
            if i % 10 == 0:
                key = next(k for k, v in e["values"].items() if isinstance(v, float))
                e["values"][key] += 1.0
                tampered.append(e["event_id"])
        return batch

    r = _run(POLICY, interceptor=tamper)
    assert r["commit_schedule"]["merged_roots"] > 0            # some batches really were held and merged
    assert r["events_rejected"] == len(tampered) > 0
    assert {reason for _, reason in r["rejected"]} == {"hash_mismatch"}
    assert sorted(eid for eid, _ in r["rejected"]) == sorted(tampered)


def test_commit_scheduling_needs_merkle_batch_mode():
    from src.pipeline import run

    with pytest.raises(ValueError):
        run(experiment="test", blockchain="per_event", n_rows=10, commit_policy=POLICY, log=lambda *_: None)


def _besu_ready():
    from src.common.qbft import BESU

    return BESU.exists()


@pytest.mark.skipif(not _besu_ready(), reason="needs Besu (scripts/setup_besu.py)")
def test_ai_scheduling_on_the_qbft_network():
    r = _run(POLICY, chain_backend="qbft")
    assert r["events_processed"] == ROWS and r["events_rejected"] == 0
    assert r["chain_network"]["consensus"]["consistent"]
    assert r["commit_schedule"]["roots"] == r["chain"]["device_commit"]["tx_count"] == _offline_roots(POLICY)
