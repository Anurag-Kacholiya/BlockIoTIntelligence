"""Cloud Intelligence runtime: consolidates fog batches, runs the global model, produces analytics (ADR §4.2, §7.6)."""

from __future__ import annotations

import time

import pandas as pd

from src.cloud.evaluate import classification_metrics, confusion
from src.cloud.model_registry import DeployedModel
from src.common.schemas import Layer


class CloudNode:
    layer = Layer.CLOUD

    def __init__(self, ledger=None):
        self.model = DeployedModel(Layer.CLOUD)
        self.ledger = ledger
        self.rows: list[dict] = []
        self.alert_count = 0

    def ingest(self, fog_batch: dict, generated_at: float) -> None:
        events = fog_batch["events"]
        predictions, confidence, _ = self.model.predict(events)
        received_at = time.perf_counter()
        self.alert_count += len(fog_batch["alerts"])
        for e, pred, conf in zip(events, predictions, confidence, strict=True):
            self.rows.append({
                "event_id": e["event_id"],
                "device_id": e["device_id"],
                "edge_id": e["edge_id"],
                "attack_label": e["attack_label"],
                "attack_type": e["attack_type"],
                "device_pred": e["device_inference"]["prediction"],
                "device_attack_prob": e["device_inference"]["attack_probability"],
                "edge_pred": e["edge_inference"]["prediction"],
                "edge_attack_prob": e["edge_inference"]["attack_probability"],
                "fog_pred": e["fog_inference"]["prediction"],
                "cloud_pred": str(pred),
                "cloud_score": conf,
                # from the event's arrival: a message held at the gateway (final task 3) arrived rounds earlier
                "e2e_ms": (received_at - e.get("arrived_at", generated_at)) * 1000,
            })
        if self.ledger is not None:
            self.ledger.record_inferences(events, predictions, self.model.model_id)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)

    def accuracy_report(self) -> list[dict]:
        """Per-layer metrics against ground truth. Binary layers score Attack_label; fog/cloud score
        Attack_type and, collapsed to attack-vs-normal, Attack_label too so all four are comparable."""
        df = self.frame()
        out = []

        def add(layer, task, y_true, y_pred, score=None):
            out.append({"layer": layer, "task": task, **classification_metrics(y_true, y_pred, score)})

        add("device", "binary", df.attack_label, df.device_pred, df.device_attack_prob)
        add("edge", "binary", df.attack_label, df.edge_pred, df.edge_attack_prob)
        for layer in ("fog", "cloud"):
            add(layer, "multiclass", df.attack_type, df[f"{layer}_pred"])
            add(layer, "binary", df.attack_label, (df[f"{layer}_pred"] != "Normal").astype(int))
        return out

    def breakdown(self) -> dict:
        """Per layer: false-alarm rate on each device's normal traffic and detection rate of each attack class
        (fog/cloud count any non-Normal prediction as a detection)."""
        df = self.frame()
        flags = {"device": df.device_pred.astype(int) == 1, "edge": df.edge_pred.astype(int) == 1,
                 "fog": df.fog_pred != "Normal", "cloud": df.cloud_pred != "Normal"}
        normal, attack = df.attack_label == 0, df.attack_label == 1
        return {
            "false_alarm_rate_by_device": {
                layer: f[normal].groupby(df.device_id[normal]).mean().to_dict() for layer, f in flags.items()},
            "detection_rate_by_class": {
                layer: f[attack].groupby(df.attack_type[attack]).mean().to_dict() for layer, f in flags.items()},
            "normal_events_by_device": df.device_id[normal].value_counts().to_dict(),
            "attack_events_by_class": df.attack_type[attack].value_counts().to_dict(),
        }

    def confusion_matrix(self, layer: str = "cloud") -> dict:
        df = self.frame()
        labels = sorted(df.attack_type.unique())
        return {"labels": labels, "matrix": confusion(df.attack_type, df[f"{layer}_pred"], labels)}
