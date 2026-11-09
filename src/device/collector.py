"""Device-side sealing: canonical hash + Ed25519 signature over it (ADR §5.2, Phase 3 device workflow)."""

from __future__ import annotations

from src.common.crypto import DeviceKey, payload_hash


def device_keys(device_ids: list[str], seed: int) -> dict[str, DeviceKey]:
    """Deterministic per-device identities so repeated runs register the same public keys."""
    return {d: DeviceKey.from_seed(f"{seed}:{i}".encode()) for i, d in enumerate(device_ids)}


def seal(event: dict, key: DeviceKey) -> dict:
    digest = payload_hash(event)
    event["payload_hash"] = digest
    event["signature"] = key.sign(digest)
    event["public_key"] = key.public_bytes.hex()
    return event
