"""Model artifacts, fingerprints and provenance metadata (ADR §7.6, Phase 6, §13.2 C).

Until the on-chain registry exists (Phase 6), models/<layer>/<model_id>.json is the record of truth;
a model is loaded only if the artifact's SHA-256 still matches its registered hash.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd
import sklearn

from src.common.config import load_config, resolve
from src.common.crypto import hash_file, hash_object
from src.common.schemas import Layer, ModelMetadata


class ModelIntegrityError(RuntimeError):
    pass


def _layer_dir(layer: Layer) -> Path:
    return resolve(load_config("base")["paths"]["models"]) / layer.name.lower()


def save_model(model, *, layer: Layer, family: str, features: list[str], training_data_hash: str,
               hyperparameters: dict, metrics: dict[str, float], deploy: bool = True) -> ModelMetadata:
    directory = _layer_dir(layer)
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f".{family}.joblib.tmp"
    joblib.dump(model, tmp)
    model_hash = hash_file(tmp)
    model_id = f"{layer.name.lower()}-{family}-{model_hash.removeprefix('sha256:')[:12]}"
    artifact = directory / f"{model_id}.joblib"
    tmp.replace(artifact)

    meta = ModelMetadata(
        model_id=model_id,
        layer=layer,
        family=family,
        model_hash=model_hash,
        training_data_hash=training_data_hash,
        feature_schema_hash=hash_object(features),
        hyperparameters=hyperparameters,
        framework_version=f"scikit-learn {sklearn.__version__}",
        metrics=metrics,
        trained_at=datetime.now(UTC),
    )
    record = meta.model_dump(mode="json") | {"features": features, "artifact": artifact.name}
    (directory / f"{model_id}.json").write_text(json.dumps(record, indent=2))
    if deploy:
        (directory / "current.json").write_text(json.dumps({"model_id": model_id}))
    return meta


def load_model(layer: Layer, model_id: str | None = None) -> tuple[object, dict]:
    """Load the deployed (or named) model for a layer after verifying its fingerprint."""
    directory = _layer_dir(layer)
    model_id = model_id or json.loads((directory / "current.json").read_text())["model_id"]
    record = json.loads((directory / f"{model_id}.json").read_text())
    artifact = directory / record["artifact"]
    if hash_file(artifact) != record["model_hash"]:
        raise ModelIntegrityError(f"{artifact.name} does not match registered hash {record['model_hash']}")
    return joblib.load(artifact), record


class DeployedModel:
    """A layer's verified, registered model plus the feature columns it was trained on."""

    def __init__(self, layer: Layer, model_id: str | None = None):
        self.model, self.record = load_model(layer, model_id)
        self.features: list[str] = self.record["features"]
        self.model_id: str = self.record["model_id"]
        self.path: Path = _layer_dir(layer) / self.record["artifact"]

    def predict(self, events: list[dict]) -> tuple[list, list[float]]:
        """Return (predicted class, confidence in that class) for each event's `values`."""
        if not events:
            return [], []
        frame = pd.DataFrame.from_records([e["values"] for e in events], columns=self.features)
        proba = self.model.predict_proba(frame)
        best = proba.argmax(axis=1)
        return self.model.classes_[best].tolist(), proba.max(axis=1).tolist()
