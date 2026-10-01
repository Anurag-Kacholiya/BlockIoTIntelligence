"""Schema and label validation for the Edge-IIoTset selected views (dataset plan step 2)."""

from __future__ import annotations

import pandas as pd

# The 61 publisher-selected features plus the two targets, in file order.
EXPECTED_COLUMNS = [
    "frame.time", "ip.src_host", "ip.dst_host", "arp.dst.proto_ipv4", "arp.opcode", "arp.hw.size",
    "arp.src.proto_ipv4", "icmp.checksum", "icmp.seq_le", "icmp.transmit_timestamp", "icmp.unused",
    "http.file_data", "http.content_length", "http.request.uri.query", "http.request.method",
    "http.referer", "http.request.full_uri", "http.request.version", "http.response", "http.tls_port",
    "tcp.ack", "tcp.ack_raw", "tcp.checksum", "tcp.connection.fin", "tcp.connection.rst",
    "tcp.connection.syn", "tcp.connection.synack", "tcp.dstport", "tcp.flags", "tcp.flags.ack", "tcp.len",
    "tcp.options", "tcp.payload", "tcp.seq", "tcp.srcport", "udp.port", "udp.stream", "udp.time_delta",
    "dns.qry.name", "dns.qry.name.len", "dns.qry.qu", "dns.qry.type", "dns.retransmission",
    "dns.retransmit_request", "dns.retransmit_request_in", "mqtt.conack.flags", "mqtt.conflag.cleansess",
    "mqtt.conflags", "mqtt.hdrflags", "mqtt.len", "mqtt.msg_decoded_as", "mqtt.msg", "mqtt.msgtype",
    "mqtt.proto_len", "mqtt.protoname", "mqtt.topic", "mqtt.topic_len", "mqtt.ver", "mbtcp.len",
    "mbtcp.trans_id", "mbtcp.unit_id", "Attack_label", "Attack_type",
]

# Normal + the fourteen attacks of the Edge-IIoTset paper.
ATTACK_TYPES = {
    "Normal", "Backdoor", "DDoS_HTTP", "DDoS_ICMP", "DDoS_TCP", "DDoS_UDP", "Fingerprinting", "MITM",
    "Password", "Port_Scanning", "Ransomware", "SQL_injection", "Uploading", "Vulnerability_scanner", "XSS",
}


class SchemaError(ValueError):
    pass


def validate(df: pd.DataFrame) -> dict:
    """Raise SchemaError on structural problems; return a report of softer findings."""
    cols = [c for c in df.columns if c != "source_row_id"]
    missing = [c for c in EXPECTED_COLUMNS if c not in cols]
    extra = [c for c in cols if c not in EXPECTED_COLUMNS]
    if missing or extra:
        raise SchemaError(f"missing={missing} extra={extra}")

    unknown = set(df["Attack_type"].unique()) - ATTACK_TYPES
    if unknown:
        raise SchemaError(f"unknown Attack_type values: {sorted(unknown)}")
    label = pd.to_numeric(df["Attack_label"], errors="coerce")
    if not label.isin([0, 1]).all():
        raise SchemaError("Attack_label must be 0/1")
    inconsistent = int(((label == 0) != (df["Attack_type"] == "Normal")).sum())
    if inconsistent:
        raise SchemaError(f"{inconsistent} rows where Attack_label disagrees with Attack_type")

    empty = df[cols].eq("") | df[cols].isna()
    return {
        "rows": len(df),
        "empty_cells_by_column": {c: int(n) for c, n in empty.sum().items() if n},
        "class_counts": df["Attack_type"].value_counts().to_dict(),
        "binary_counts": label.value_counts().astype(int).to_dict(),
    }
