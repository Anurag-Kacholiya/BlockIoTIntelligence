"""Cloud Intelligence training: fits every layer's model and the cloud candidates (ADR §7, Phase 6).

Cloud is the only layer with enough compute to train; it produces the device, edge and fog models
too, which those layers then load (and, from Phase 6, verify against the on-chain registry).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from src.cloud.evaluate import classification_metrics
from src.cloud.model_registry import save_model
from src.common.config import load_config, resolve
from src.common.schemas import Layer, ModelMetadata
from src.edge.preprocessing import build_preprocessor

FAMILIES = {
    "decision_tree": DecisionTreeClassifier,
    "random_forest": RandomForestClassifier,
    "gradient_boosting": HistGradientBoostingClassifier,
    "mlp": MLPClassifier,
}
TARGET_BY_TASK = {"binary": "Attack_label", "multiclass": "Attack_type"}


@dataclass
class TrainingData:
    view: str
    train: pd.DataFrame
    validation: pd.DataFrame
    train_hash: str          # file hash of the full train split, from its manifest
    numeric: list[str]
    categorical: list[str]
    layer_features: dict[str, list[str]]


def load_training_data(seed: int) -> TrainingData:
    cfg = load_config("models")["training"]
    paths = load_config("datasets")["paths"]
    view = cfg["view"]
    split_dir = resolve(paths["splits"]) / view
    manifest = json.loads((resolve(paths["manifests"]) / f"{view}_preparation.json").read_text())
    train = pd.read_parquet(split_dir / "train.parquet")
    validation = pd.read_parquet(split_dir / "validation.parquet")
    if cfg.get("max_train_rows") and len(train) > cfg["max_train_rows"]:
        train, _ = train_test_split(
            train, train_size=cfg["max_train_rows"], stratify=train["Attack_type"], random_state=seed
        )
    return TrainingData(
        view=view,
        train=train,
        validation=validation,
        train_hash=manifest["file_hashes"]["splits/train"],
        numeric=manifest["cleaning"]["numeric_columns"],
        categorical=manifest["cleaning"]["categorical_columns"],
        layer_features={k: v["features"] for k, v in manifest["views"].items()},
    )


def _fit(family: str, params: dict, features: list[str], data: TrainingData, target: str, seed: int):
    numeric = [c for c in features if c in data.numeric]
    categorical = [c for c in features if c in data.categorical]
    params = dict(params) | {"random_state": params.get("random_state", seed)}
    model = Pipeline([("pre", build_preprocessor(numeric, categorical)), ("clf", FAMILIES[family](**params))])
    start = time.perf_counter()
    model.fit(data.train[features], data.train[target])
    fit_s = time.perf_counter() - start
    if hasattr(model[-1], "n_jobs"):
        model[-1].n_jobs = 1  # streaming inference is per micro-batch; process pools cost more than they save

    start = time.perf_counter()
    X_val = data.validation[features]
    pred = model.predict(X_val)
    score = model.predict_proba(X_val)[:, 1] if target == "Attack_label" else None
    metrics = classification_metrics(data.validation[target], pred, score)
    metrics |= {"fit_seconds": fit_s, "validation_predict_seconds": time.perf_counter() - start}
    return model, metrics


def train_all(seed: int = 42, log=print) -> dict[str, ModelMetadata]:
    cfg = load_config("models")
    data = load_training_data(seed)
    log(f"training on {len(data.train):,} rows of the {data.view} train split")
    deployed: dict[str, ModelMetadata] = {}

    for layer in (Layer.DEVICE, Layer.EDGE, Layer.FOG):
        spec = cfg[layer.name.lower()]
        features = data.layer_features[layer.name.lower()]
        model, metrics = _fit(spec["family"], spec["params"], features, data, TARGET_BY_TASK[spec["task"]], seed)
        deployed[layer.name] = save_model(
            model, layer=layer, family=spec["family"], features=features,
            training_data_hash=data.train_hash, hyperparameters=spec["params"], metrics=metrics,
        )
        log(f"{layer.name:6s} {spec['family']:18s} {spec['task']:10s} f1_macro={metrics['f1_macro']:.4f}")

    # Cloud: train every candidate, register all, deploy the best on the validation split.
    features = data.layer_features["cloud"]
    target = TARGET_BY_TASK[cfg["cloud"]["task"]]
    best = None
    selection = cfg["training"]["selection_metric"]
    for family, params in cfg["cloud"]["candidates"].items():
        model, metrics = _fit(family, params, features, data, target, seed)
        meta = save_model(
            model, layer=Layer.CLOUD, family=family, features=features,
            training_data_hash=data.train_hash, hyperparameters=params, metrics=metrics, deploy=False,
        )
        log(f"CLOUD  {family:18s} multiclass f1_macro={metrics['f1_macro']:.4f} fit={metrics['fit_seconds']:.0f}s")
        if best is None or metrics[selection] > best.metrics[selection]:
            best = meta
    (resolve(load_config("base")["paths"]["models"]) / "cloud" / "current.json").write_text(
        json.dumps({"model_id": best.model_id})
    )
    deployed["CLOUD"] = best
    log(f"cloud deployed: {best.model_id}")
    return deployed
