"""ADR §14.3 Test 4 — model tamper: a modified artifact must not load."""

import json

import pytest

from src.cloud import model_registry
from src.cloud.model_registry import ModelIntegrityError, load_model, save_model
from src.common.schemas import Layer


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr(model_registry, "_layer_dir", lambda layer: tmp_path / layer.name.lower())
    return tmp_path


def _save():
    return save_model(
        {"weights": [1, 2, 3]}, layer=Layer.EDGE, family="toy", features=["a", "b"],
        training_data_hash="sha256:00", hyperparameters={}, metrics={"f1_macro": 1.0},
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
