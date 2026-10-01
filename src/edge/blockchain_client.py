"""Edge blockchain actions: verify identity, signature and on-chain commitment; record processing (ADR §6.4, Phase 4).

verify_event returns None (accept) or the reason the event is rejected. The order of checks decides
which control is credited with a detection in the security experiment.
"""

from __future__ import annotations

from src.common import merkle
from src.common.blockchain import Chain, h32, id32
from src.common.crypto import hash_object, payload_hash, sha256_hex, verify_signature
from src.common.schemas import Layer

ZERO = b"\x00" * 32


class EdgeChainClient:
    def __init__(self, chain: Chain, sender: str, mode: str = "per_event"):
        self.chain, self.sender, self.mode = chain, sender, mode
        self._devices: dict[str, tuple] = {}
        self._roots: dict[str, bytes] = {}
        self._processed_batches: set[str] = set()   # batch mode: batches this edge has already recorded
        self._batch_checked: dict[str, bool] = {}    # batch mode: on-chain "processed" lookup, once per batch

    def _device(self, device_id: str) -> tuple:
        if device_id not in self._devices:   # (pubKeyHash, registeredAt, active); cached per run
            self._devices[device_id] = tuple(self.chain.call("edge_device_lookup", "devices", id32(device_id)))
        return self._devices[device_id]

    def verify_event(self, event: dict) -> str | None:
        pub_key_hash, _, active = self._device(event["device_id"])
        if not active:
            return "unregistered_device"
        if "signature" not in event or "public_key" not in event:
            return "unsigned"
        public_key = bytes.fromhex(event["public_key"])
        if h32(sha256_hex(public_key)) != pub_key_hash:
            return "identity_mismatch"          # key is not the one registered for this device

        recomputed = payload_hash(event)
        if self.mode == "per_event":
            commitment_id = id32(event["event_id"])
            committed = self.chain.call("edge_verify", "commitments", commitment_id)[1]
            if committed == ZERO:
                return "not_committed"
            if committed != h32(recomputed):
                return "hash_mismatch"          # payload changed after the device committed it
        else:
            commitment_id = id32(event["batch_id"])
            if event["batch_id"] not in self._roots:
                self._roots[event["batch_id"]] = self.chain.call("edge_verify", "commitments", commitment_id)[1]
            committed = self._roots[event["batch_id"]]
            if committed == ZERO:
                return "not_committed"
            if merkle.root_from_proof(h32(recomputed), event["merkle_proof"]) != committed:
                return "hash_mismatch"

        if not verify_signature(public_key, recomputed, event["signature"]):
            return "bad_signature"
        if self.mode == "batch":
            batch_id = event["batch_id"]
            if batch_id not in self._processed_batches and batch_id not in self._batch_checked:
                self._batch_checked[batch_id] = (
                    self.chain.call("edge_replay_check", "processed", commitment_id) != ZERO)
            if batch_id in self._processed_batches or self._batch_checked.get(batch_id):
                return "replay_already_processed"
            return None
        if self.chain.call("edge_replay_check", "processed", commitment_id) != ZERO:
            return "replay_already_processed"   # another edge already consumed this event (shared ledger state)
        return None

    def commit_processed(self, events: list[dict]) -> None:
        if not events:
            return
        if self.mode == "per_event":
            calls = [[id32(e["event_id"]), h32(e["payload_hash"]), h32(self._processed_hash(e)), int(Layer.EDGE)]
                     for e in events]
        else:
            batches: dict[str, list[dict]] = {}
            for e in events:
                batches.setdefault(e["batch_id"], []).append(e)
            calls = [[id32(b), self._roots[b], h32(hash_object([self._processed_hash(e) for e in group])),
                      int(Layer.EDGE)] for b, group in batches.items()]
            self._processed_batches.update(batches)
        self.chain.send_many("edge_processed", "recordProcessing", calls, self.sender)

    @staticmethod
    def _processed_hash(event: dict) -> str:
        return hash_object({"parent": event["payload_hash"], "edge_id": event["edge_id"],
                            "inference": event["edge_inference"]})
