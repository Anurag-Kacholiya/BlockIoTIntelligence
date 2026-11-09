"""Cloud Intelligence trains the gateway's traffic forecaster (final task 3, RQ-11 AI-driven blockchain).

The forecaster answers, for a device with an open Merkle batch: will it send again within the next r rounds? Its
training data are replay-like streams cut from the **train** windows of the time split (the windows the layer models
were trained on), at many device counts; the validation windows score it. The test window, which every experiment
replays, is never used. Features come from `src.device.commit_policy.TrafficHistory`, the same code the gateway runs,
so training and serving cannot drift apart.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from src.cloud.model_registry import FORECASTER, save_model
from src.common.config import load_config, resolve
from src.common.crypto import hash_object
from src.common.schemas import Layer, ModelMetadata
from src.common.storage import read_parquet
from src.data.preparation.realistic import captures, timing_stream, window_packets
from src.device.commit_policy import FEATURES, TrafficHistory, event_seconds, future_rounds, timing_events
from src.device.simulator import RealtimeReplay


def session_cuts() -> pd.DataFrame:
    return read_parquet(resolve(load_config("datasets")["paths"]["splits"]) / "real" / "session_cuts.parquet")


def samples(sim, round_size: int, max_hold: int) -> pd.DataFrame:
    """One row per (round, device that sent in the last max_hold rounds, horizon r): FEATURES and the label "sends
    within the next r rounds". These are the states the gateway asks about: a pending batch's device sent at most
    hold_rounds - 1 rounds ago, and may wait hold_rounds - age more rounds."""
    history = TrafficHistory(sim.device_ids)
    future = future_rounds(sim.device_of, round_size)
    names = np.array(sim.device_ids)
    n_rounds = -(-len(sim) // round_size)
    parts = []
    for k, events in enumerate(timing_events(sim, round_size)):
        history.observe([e["device_id"] for e in events], [event_seconds(e) for e in events])
        if k == n_rounds - 1:                          # the last round commits everything: nothing to decide
            break
        since = history.round - history.last
        recent = np.nonzero((history.last >= 0) & (since <= max_hold - 1))[0]
        devices, remaining = [], []
        for i in recent:
            for r in range(1, max_hold - since[i] + 1):
                devices.append(names[i])
                remaining.append(r)
        if not devices:
            continue
        x = history.features(devices, remaining)
        y = [any(k + j in future[d] for j in range(1, r + 1)) for d, r in zip(devices, remaining, strict=True)]
        parts.append(pd.DataFrame(x, columns=FEATURES).assign(y=np.array(y, dtype=int), round=k))
    return pd.concat(parts, ignore_index=True)


def window_samples(window: str, per_size: int, cfg: dict, log=print) -> pd.DataFrame:
    """Samples from `per_size` random streams per stream size, each at every replica count of the config."""
    rng = np.random.default_rng(cfg["streams"]["seed"] + (window == "validation"))
    cuts = session_cuts()
    packets = {c: window_packets(c, window, cuts) for c in captures()}
    out = []
    for rows in cfg["streams"]["rows"]:
        for s in range(per_size):
            stream = timing_stream(packets, rows, rng)
            for k in cfg["streams"]["replicas"]:
                sim = RealtimeReplay(stream, replicas=k)
                out.append(samples(sim, cfg["round_size"], cfg["max_hold_rounds"])
                           .assign(stream=f"{window}-{rows}-{s}", devices=len(sim.device_ids)))
    df = pd.concat(out, ignore_index=True)
    log(f"{window}: {len(df):,} samples from {len(cfg['streams']['rows']) * per_size} streams, positive rate"
        f" {df.y.mean():.3f}")
    return df


def rate_probability(x: np.ndarray) -> np.ndarray:
    """Non-learned reference: Poisson arrivals at the device's recent rate, P(at least one) = 1 - exp(-expected)."""
    expected = np.nan_to_num(x[:, FEATURES.index("expected_msgs")], nan=0.0)
    return 1.0 - np.exp(-expected)


def forecast_metrics(y: np.ndarray, p: np.ndarray, x: np.ndarray) -> dict[str, float]:
    """The forecaster against two references: "it sent in this round" (persistence) and the Poisson rate."""
    persistence = (x[:, FEATURES.index("msgs_this_round")] > 0).astype(float)
    return {"samples": float(len(y)), "positive_rate": float(y.mean()), "roc_auc": float(roc_auc_score(y, p)),
            "brier": float(brier_score_loss(y, p)), "log_loss": float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))),
            "accuracy": float(((p >= 0.5) == y).mean()),
            "persistence_roc_auc": float(roc_auc_score(y, persistence)),
            "persistence_accuracy": float((persistence == y).mean()),
            "rate_roc_auc": float(roc_auc_score(y, rate_probability(x))),
            "rate_brier": float(brier_score_loss(y, rate_probability(x)))}


class RateForecaster:
    """The Poisson-rate reference as a forecaster, so the policy can run without learning (offline comparison)."""

    model_id = "poisson-rate"

    @staticmethod
    def probability(history, devices, remaining) -> np.ndarray:
        return rate_probability(history.features(devices, remaining))


def train_forecaster(log=print) -> ModelMetadata:
    cfg = load_config("models")["forecaster"]
    train = window_samples("train", cfg["streams"]["train_per_size"], cfg, log)
    validation = window_samples("validation", cfg["streams"]["validation_per_size"], cfg, log)
    params = dict(cfg["params"]) | {"random_state": cfg["streams"]["seed"]}
    model = HistGradientBoostingClassifier(**params)
    start = time.perf_counter()
    model.fit(train[FEATURES].to_numpy(), train.y.to_numpy())
    fit_s = time.perf_counter() - start
    x = validation[FEATURES].to_numpy()
    metrics = forecast_metrics(validation.y.to_numpy(), model.predict_proba(x)[:, 1], x)
    metrics |= {"fit_seconds": fit_s, "train_samples": float(len(train))}
    log(f"forecaster: validation AUC {metrics['roc_auc']:.4f} (persistence {metrics['persistence_roc_auc']:.4f},"
        f" Poisson rate {metrics['rate_roc_auc']:.4f}), Brier {metrics['brier']:.4f}, fit {fit_s:.0f} s")
    cuts_manifest = resolve(load_config("datasets")["paths"]["splits"]) / "real" / "session_cuts.manifest.json"
    training_hash = hash_object({"session_cuts": cuts_manifest.read_text(), "streams": cfg["streams"],
                                 "round_size": cfg["round_size"], "max_hold_rounds": cfg["max_hold_rounds"],
                                 "samples": len(train)})
    return save_model(model, layer=Layer.DEVICE, family=cfg["family"], features=FEATURES,
                      training_data_hash=training_hash, hyperparameters=params, metrics=metrics, kind=FORECASTER)
