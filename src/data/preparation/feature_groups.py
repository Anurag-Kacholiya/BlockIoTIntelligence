"""Feature taxonomy and the layer-specific views derived from one canonical table (dataset plan step 6)."""

from __future__ import annotations

# Header-level fields a constrained device can read without parsing application payloads.
DEVICE_FEATURES = [
    "tcp.len", "tcp.flags", "tcp.flags.ack", "tcp.connection.syn", "tcp.connection.synack",
    "tcp.connection.fin", "tcp.connection.rst", "udp.time_delta", "icmp.seq_le",
    "arp.opcode", "arp.hw.size", "mqtt.len", "mbtcp.len",
]


def protocol_of(column: str) -> str:
    return column.split(".", 1)[0]


def view_spec(numeric: list[str], categorical: list[str]) -> dict[str, dict]:
    """Column set and target(s) for each intelligence layer, all drawn from the same cleaned rows."""
    all_features = numeric + categorical
    return {
        "device": {"features": [c for c in DEVICE_FEATURES if c in numeric], "targets": ["Attack_label"]},
        "edge": {"features": all_features, "targets": ["Attack_label"]},
        # Windowed temporal features (1/5/30/60 s) are appended by the fog service from replay time.
        "fog": {"features": all_features, "targets": ["Attack_type", "Attack_label"]},
        "cloud": {"features": all_features, "targets": ["Attack_label", "Attack_type"]},
    }
