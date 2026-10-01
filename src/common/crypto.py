"""Canonical hashing and device signatures (ADR §5.2).

Never hash a Python object's default serialization: normalize, serialize as canonical JSON
(sorted keys, compact separators, UTF-8, no NaN), then SHA-256.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

HASH_PREFIX = "sha256:"

# Fields that define an event's content (ADR §5.2). Hashes and signatures are excluded by construction.
PAYLOAD_FIELDS = ("event_id", "device_id", "timestamp", "sequence_number", "values")


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if hasattr(value, "item"):  # numpy scalar
        return value.item()
    return value


def canonical_json(obj: Any) -> bytes:
    return json.dumps(
        _normalize(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return HASH_PREFIX + hashlib.sha256(data).hexdigest()


def hash_object(obj: Any) -> str:
    return sha256_hex(canonical_json(obj))


def payload_hash(event: dict[str, Any]) -> str:
    """Content hash of a telemetry event, computed only over PAYLOAD_FIELDS."""
    return hash_object({k: event[k] for k in PAYLOAD_FIELDS})


def hash_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return HASH_PREFIX + h.hexdigest()


class DeviceKey:
    """Ed25519 identity for one logical device."""

    def __init__(self, private_key: Ed25519PrivateKey | None = None):
        self._key = private_key or Ed25519PrivateKey.generate()

    @classmethod
    def from_seed(cls, seed: bytes) -> DeviceKey:
        """Deterministic key for reproducible experiments: seed is hashed to 32 bytes."""
        return cls(Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed).digest()))

    @property
    def public_bytes(self) -> bytes:
        return self._key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    @property
    def public_key_hash(self) -> str:
        return sha256_hex(self.public_bytes)

    def sign(self, digest: str) -> str:
        return self._key.sign(digest.encode("ascii")).hex()


def verify_signature(public_bytes: bytes, digest: str, signature_hex: str) -> bool:
    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_bytes)
        public_key.verify(bytes.fromhex(signature_hex), digest.encode("ascii"))
        return True
    except (InvalidSignature, ValueError):
        return False
