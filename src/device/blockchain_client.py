"""Device blockchain actions: seal each event and commit its hash on-chain before publishing (ADR §6.3, Phase 3).

Modes:
  per_event  one commitData transaction per event (the ADR's reference design)
  batch      one commitBatch per device per micro-batch, carrying a Merkle root; each event travels with
             its inclusion proof (AI/aggregation-driven cost reduction, ADR §13.1 D)

In batch mode a commit scheduler (final task 3, src/device/commit_policy.py) may keep a device's batch open for more
micro-batches, so one root covers more messages; the events it holds are sealed now and committed later.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from src.common import merkle
from src.common.blockchain import Chain, h32, id32
from src.common.crypto import DeviceKey
from src.common.schemas import Layer
from src.device.collector import seal

if TYPE_CHECKING:
    from src.device.commit_policy import CommitScheduler


def epoch_ms(event: dict) -> int:
    return int(event["timestamp"].timestamp() * 1000)


class DeviceChainClient:
    def __init__(self, chain: Chain, keys: dict[str, DeviceKey], sender: str, mode: str = "per_event",
                 scheduler: CommitScheduler | None = None):
        if mode not in ("per_event", "batch"):
            raise ValueError(mode)
        if scheduler is not None and mode != "batch":
            raise ValueError("a commit scheduler decides when Merkle batches close: it needs mode='batch'")
        self.chain, self.keys, self.sender, self.mode, self.scheduler = chain, keys, sender, mode, scheduler

    def commit_events(self, events: list[dict], final: bool = False) -> list[dict]:
        """Seal the micro-batch's events and commit them; returns the events committed now (all of them, unless the
        scheduler keeps some batches open; final=True, the stream's last micro-batch, commits everything)."""
        for e in events:
            seal(e, self.keys[e["device_id"]])
        if self.scheduler is not None:
            events = self.scheduler.step(events, final)
        if self.mode == "per_event":
            self.chain.send_many("device_commit", "commitData", [
                [id32(e["event_id"]), id32(e["device_id"]), h32(e["payload_hash"]), int(Layer.DEVICE), epoch_ms(e)]
                for e in events
            ], self.sender)
            return events

        by_device: dict[str, list[dict]] = defaultdict(list)
        for e in events:
            by_device[e["device_id"]].append(e)
        calls = []
        for device_id, group in by_device.items():
            root, proofs = merkle.build([h32(e["payload_hash"]) for e in group])
            batch_id = f"batch:{group[0]['event_id']}"
            for e, proof in zip(group, proofs, strict=True):
                e["batch_id"] = batch_id
                e["merkle_proof"] = proof
            calls.append([id32(batch_id), id32(device_id), root, len(group), epoch_ms(group[0])])
        self.chain.send_many("device_commit", "commitBatch", calls, self.sender)
        return events
