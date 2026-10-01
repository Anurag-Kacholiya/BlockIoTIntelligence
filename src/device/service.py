"""Device Intelligence: local lightweight inference on header-level features (ADR §4.2, §7.3, Phase 3).

`ledger` is None in the baseline; Phase 3 passes a blockchain client that seals and commits events.
"""

from __future__ import annotations

from src.cloud.model_registry import DeployedModel
from src.common.schemas import Layer


class DeviceLayer:
    layer = Layer.DEVICE

    def __init__(self, ledger=None):
        self.model = DeployedModel(Layer.DEVICE)
        self.ledger = ledger

    def process(self, events: list[dict]) -> list[dict]:
        predictions, confidence = self.model.predict(events)
        for event, pred, conf in zip(events, predictions, confidence, strict=True):
            event["device_inference"] = {"model_id": self.model.model_id, "prediction": int(pred), "score": conf}
        if self.ledger is not None:
            self.ledger.commit_events(events)
        return events
