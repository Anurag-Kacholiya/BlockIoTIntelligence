"""Device-side sealing: canonical hash + Ed25519 signature over it (ADR §5.2, Phase 3 device workflow)."""

from __future__ import annotations

from src.common.crypto import DeviceKey, payload_hash


def device_keys(n_devices: int, seed: int) -> dict[str, DeviceKey]:
    """Deterministic per-device identities so repeated runs register the same public keys."""
    from src.device.simulator import DeviceSimulator

    return {DeviceSimulator.device_id(i): DeviceKey.from_seed(f"{seed}:{i}".encode()) for i in range(n_devices)}


def seal(event: dict, key: DeviceKey) -> dict:
    digest = payload_hash(event)
    event["payload_hash"] = digest
    event["signature"] = key.sign(digest)
    event["public_key"] = key.public_bytes.hex()
    return event
