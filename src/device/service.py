"""Device Intelligence: local lightweight inference on header-level features (ADR §4.2, §7.3, Phase 3).

`ledger` is None in the baseline; Phase 3 passes a blockchain client that seals and commits events. With a commit
scheduler (final task 3) the ledger may hold some events for later micro-batches: process returns the events that
leave the device layer now.
"""

from __future__ import annotations

from src.cloud.model_registry import DeployedModel
from src.common.schemas import Layer


class DeviceLayer:
    layer = Layer.DEVICE

    def __init__(self, ledger=None):
        self.model = DeployedModel(Layer.DEVICE)
        self.ledger = ledger

    def process(self, events: list[dict], final: bool = False) -> list[dict]:
        predictions, confidence, attack_prob = self.model.predict(events)
        for event, pred, conf, p_attack in zip(events, predictions, confidence, attack_prob, strict=True):
            event["device_inference"] = {"model_id": self.model.model_id, "prediction": int(pred), "score": conf,
                                         "attack_probability": p_attack}
        if self.ledger is not None:
            return self.ledger.commit_events(events, final=final)
        return events
