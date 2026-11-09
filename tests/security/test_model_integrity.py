"""ADR §14.3 Test 4 — model tamper: a modified artifact must not load."""

import json

import pytest

from src.cloud import model_registry
from src.cloud.model_registry import ModelIntegrityError, load_model, save_model
from src.common.schemas import Layer


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr(model_registry, "layer_dir",
                        lambda layer, kind="": tmp_path / (layer.name.lower() + (f"_{kind}" if kind else "")))
    return tmp_path


def _save(kind=""):
    return save_model(
        {"weights": [1, 2, 3]}, layer=Layer.EDGE, family="toy", features=["a", "b"],
        training_data_hash="sha256:00", hyperparameters={}, metrics={"f1_macro": 1.0}, kind=kind,
    )


def test_registered_model_loads(registry):
    meta = _save()
    model, record = load_model(Layer.EDGE)
    assert model == {"weights": [1, 2, 3]} and record["model_id"] == meta.model_id


def test_tampered_model_is_refused(registry):
    meta = _save()
    record = json.loads((registry / "edge" / f"{meta.model_id}.json").read_text())
    with open(registry / "edge" / record["artifact"], "ab") as f:
        f.write(b"\x00")
    with pytest.raises(ModelIntegrityError):
        load_model(Layer.EDGE)


def test_a_model_of_another_kind_has_its_own_folder_and_is_checked_too(registry):
    """Final task 3: the gateway's forecaster is a model kind of its own; it never replaces the layer's classifier,
    and a tampered one is refused like any other."""
    classifier, forecaster = _save(), _save(kind="forecaster")
    assert load_model(Layer.EDGE)[1]["model_id"] == classifier.model_id
    assert load_model(Layer.EDGE, kind="forecaster")[1]["model_id"] == forecaster.model_id
    record = json.loads((registry / "edge_forecaster" / f"{forecaster.model_id}.json").read_text())
    with open(registry / "edge_forecaster" / record["artifact"], "ab") as f:
        f.write(b"\x00")
    with pytest.raises(ModelIntegrityError):
        load_model(Layer.EDGE, kind="forecaster")
