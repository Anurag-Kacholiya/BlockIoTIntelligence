"""Edge Intelligence: gate, preprocess + binary attack inference, forward to fog (ADR §4.2, §7.4, Phase 4).

Preprocessing (scaling/encoding, fitted on train only) is inside the registered model pipeline, so
the edge applies exactly the transformation the model was trained with.
"""

from __future__ import annotations

from src.cloud.model_registry import DeployedModel
from src.common.schemas import Layer
from src.edge.ingest import IngestGate


class EdgeNode:
    layer = Layer.EDGE

    def __init__(self, edge_id: str, ledger=None, validate_schema: bool = True):
        self.edge_id = edge_id
        self.model = DeployedModel(Layer.EDGE)
        self.gate = IngestGate(validate_schema)
        self.ledger = ledger
        self.rejected: list[tuple[str, str]] = []   # (event_id, reason)

    def process(self, events: list[dict]) -> list[dict]:
        accepted = []
        for event in events:
            reason = self.gate.check(event)
            if reason is None and self.ledger is not None:
                reason = self.ledger.verify_event(event)
            if reason is None:
                self.gate.commit(event)
                accepted.append(event)
            else:
                self.rejected.append((event["event_id"], reason))

        predictions, confidence = self.model.predict(accepted)
        for event, pred, conf in zip(accepted, predictions, confidence, strict=True):
            event["edge_id"] = self.edge_id
            event["edge_inference"] = {"model_id": self.model.model_id, "prediction": int(pred), "score": conf}
        if self.ledger is not None:
            self.ledger.commit_processed(accepted)
        return accepted
