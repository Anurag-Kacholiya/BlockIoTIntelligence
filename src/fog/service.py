"""Fog Intelligence: aggregate edge streams, multiclass attack detection, alerts (ADR §4.2, §7.5, Phase 5)."""

from __future__ import annotations

import uuid

from src.cloud.model_registry import DeployedModel
from src.common.config import load_config
from src.common.schemas import AttackAlert, Layer
from src.fog.traffic_analysis import TrafficAnalyzer


class FogNode:
    layer = Layer.FOG

    def __init__(self, fog_id: str, ledger=None, flood_events_per_second: float = 50.0):
        self.fog_id = fog_id
        self.model = DeployedModel(Layer.FOG)
        windows = load_config("datasets")["edge_iiotset"]["temporal"]["windows_seconds"]
        self.traffic = TrafficAnalyzer(windows, flood_events_per_second)
        self.ledger = ledger
        self.alerts: list[AttackAlert] = []

    def process(self, edge_batches: list[list[dict]]) -> dict:
        """Merge the batches from all connected edges and analyse them together."""
        events = [e for batch in edge_batches for e in batch]
        predictions, confidence = self.model.predict(events)
        batch_alerts = []
        for event, pred, conf in zip(events, predictions, confidence, strict=True):
            stats = self.traffic.observe(event["device_id"], event["timestamp"])
            event["fog_inference"] = {"model_id": self.model.model_id, "prediction": str(pred), "score": conf}
            event["traffic"] = stats
            if pred != "Normal" or self.traffic.is_flooding(stats):
                batch_alerts.append(AttackAlert(
                    alert_id=str(uuid.uuid4()), fog_id=self.fog_id, trace_id=event["trace_id"],
                    event_ids=[event["event_id"]], attack_type=str(pred) if pred != "Normal" else "Flooding",
                    confidence=conf, timestamp=event["timestamp"],
                ))
        self.alerts += batch_alerts
        if self.ledger is not None:
            self.ledger.audit_alerts(batch_alerts)
        return {"fog_id": self.fog_id, "events": events, "alerts": batch_alerts,
                "source_edges": sorted({e["edge_id"] for e in events})}
