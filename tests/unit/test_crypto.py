from datetime import UTC, datetime

from src.common.crypto import DeviceKey, canonical_json, payload_hash, verify_signature


def _event(**overrides):
    event = {
        "event_id": "evt-1",
        "device_id": "device-0001",
        "timestamp": datetime(2026, 9, 29, 10, 0, tzinfo=UTC),
        "sequence_number": 7,
        "values": {"tcp.len": 12.0, "mqtt.len": 0.0},
        "signature": "ignored",
    }
    event.update(overrides)
    return event


def test_canonical_json_is_key_order_independent():
    assert canonical_json({"b": 1, "a": {"y": 2, "x": 1}}) == canonical_json({"a": {"x": 1, "y": 2}, "b": 1})


def test_payload_hash_ignores_non_payload_fields():
    assert payload_hash(_event()) == payload_hash(_event(signature="different"))


def test_payload_hash_detects_tampering():
    # ADR §6.4 tampering experiment: any change to a value changes the hash.
    tampered = _event(values={"tcp.len": 13.0, "mqtt.len": 0.0})
    assert payload_hash(_event()) != payload_hash(tampered)


def test_signature_roundtrip_and_rejection():
    key, other = DeviceKey.from_seed(b"device-0001"), DeviceKey.from_seed(b"device-0002")
    digest = payload_hash(_event())
    sig = key.sign(digest)
    assert verify_signature(key.public_bytes, digest, sig)
    assert not verify_signature(other.public_bytes, digest, sig)          # invalid signer
    assert not verify_signature(key.public_bytes, payload_hash(_event(sequence_number=8)), sig)


def test_seeded_keys_are_deterministic():
    assert DeviceKey.from_seed(b"d1").public_key_hash == DeviceKey.from_seed(b"d1").public_key_hash
