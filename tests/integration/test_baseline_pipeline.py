"""End-to-end baseline (ADR §17.3, without the blockchain assertions that arrive in Phase 2+)."""

import pytest

from src.common.config import load_config, resolve

VIEW = load_config("models")["training"]["view"]
READY = (resolve(load_config("datasets")["paths"]["splits"]) / VIEW / "test.parquet").exists() and (
    resolve("models/cloud/current.json").exists()
)

pytestmark = [
    pytest.mark.dataset,
    pytest.mark.skipif(not READY, reason="run scripts/prepare_dataset.py and scripts/train_models.py first"),
]


@pytest.fixture(scope="module")
def result():
    from src.pipeline import run

    return run(experiment="test", n_rows=2000, devices=5, edges=2, fogs=1, batch_size=128, log=lambda *_: None)


def test_every_generated_event_reaches_the_cloud(result):
    assert result["events_in"] == 2000
    assert result["events_processed"] == 2000
    assert result["events_rejected"] == 0


def test_all_four_layers_produce_predictions(result):
    layers = {(r["layer"], r["task"]) for r in result["accuracy"]}
    assert {("device", "binary"), ("edge", "binary"), ("fog", "multiclass"), ("cloud", "multiclass")} <= layers


def test_models_beat_majority_class(result):
    # Majority class (Normal) is ~71% of the DNN test split.
    by = {(r["layer"], r["task"]): r for r in result["accuracy"]}
    assert by[("edge", "binary")]["accuracy"] > 0.8
    assert by[("cloud", "multiclass")]["accuracy"] > 0.8


def test_latency_recorded_for_each_stage(result):
    assert {"device", "edge", "fog", "cloud", "batch_end_to_end"} <= set(result["latency_ms"])
