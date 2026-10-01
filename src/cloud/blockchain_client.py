"""Cloud blockchain actions: model registry and inference provenance (ADR §6.5, §13.2 C/D, Phase 6)."""

from __future__ import annotations

import time

from src.common.blockchain import Chain, h32, id32
from src.common.crypto import hash_file, hash_object


class ModelNotRegistered(RuntimeError):
    pass


class CloudChainClient:
    def __init__(self, chain: Chain, sender: str):
        self.chain, self.sender = chain, sender

    def register_model(self, record: dict) -> None:
        self.chain.send("model_register", "registerModel", [
            id32(record["model_id"]), h32(record["model_hash"]), int(record["layer"]), record["model_id"],
        ], self.sender)

    def verify_model(self, record: dict, artifact_path) -> None:
        """Accept an artifact only if its current SHA-256 equals the hash registered on-chain.
        The local JSON record is not trusted: an attacker who can replace the file can edit it too."""
        on_chain = self.chain.call("model_verify", "models", id32(record["model_id"]))[0]
        if on_chain == b"\x00" * 32:
            raise ModelNotRegistered(record["model_id"])
        if h32(hash_file(artifact_path)) != on_chain:
            raise ModelNotRegistered(f"{record['model_id']}: artifact hash differs from on-chain registry")

    def record_inferences(self, events: list[dict], predictions: list, model_id: str) -> None:
        if not events:
            return
        result_hash = hash_object([[e["event_id"], str(p)] for e, p in zip(events, predictions, strict=True)])
        self.chain.send("cloud_inference_record", "recordInference", [
            id32(f"inference:{events[0]['event_id']}"), id32(model_id), h32(result_hash), int(time.time() * 1000),
        ], self.sender)
