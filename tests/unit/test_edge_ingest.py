from datetime import UTC, datetime

from src.edge.ingest import IngestGate


def _accept(gate, event):
    reason = gate.check(event)
    if reason is None:
        gate.commit(event)
    return reason


def _event(event_id="e1", seq=0, device="device-0001"):
    return {
        "event_id": event_id, "device_id": device, "trace_id": event_id,
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC), "sequence_number": seq, "values": {"tcp.len": 1.0},
        "source_file": "f.csv", "source_row_id": 0, "attack_label": 0, "attack_type": "Normal",
    }


def test_accepts_in_order_events():
    gate = IngestGate()
    assert _accept(gate, _event("e1", 0)) is None
    assert _accept(gate, _event("e2", 1)) is None


def test_rejects_replayed_event():
    gate = IngestGate()
    _accept(gate, _event("e1", 0))
    assert _accept(gate, _event("e1", 0)) == "duplicate_event"


def test_rejects_sequence_regression_with_new_id():
    gate = IngestGate()
    _accept(gate, _event("e1", 5))
    assert _accept(gate, _event("e2", 5)) == "sequence_regression"


def test_sequence_is_tracked_per_device():
    gate = IngestGate()
    _accept(gate, _event("e1", 5, "device-0001"))
    assert _accept(gate, _event("e2", 0, "device-0002")) is None


def test_rejects_malformed_event():
    bad = _event() | {"sequence_number": -1}
    assert IngestGate().check(bad) == "schema"


def test_rejected_event_does_not_advance_sequence():
    # A forged event that fails a later check must not lock out the device's genuine traffic.
    gate = IngestGate()
    assert gate.check(_event("forged", 10**9)) is None     # passes the gate, then rejected elsewhere
    assert _accept(gate, _event("e1", 0)) is None
