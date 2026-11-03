"""Packet index for the Edge-IIoTset captures (final task 1, step 1).

Reads a classic-format pcap (all 24 Edge-IIoTset captures are little-endian, microsecond, Ethernet) and
returns one row per packet: real UTC timestamp, length, protocol and the IPv4 addresses/ports needed to
match CSV rows to packets. ARP packets carry their sender/target protocol addresses as src/dst.

Packets are sorted by time (captures contain some out-of-order packets), corrupt timestamps are flagged,
and each capture is split into sessions wherever two consecutive packets are further apart than a gap.
"""

from __future__ import annotations

import struct
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

PCAP_MAGIC_LE_US = b"\xd4\xc3\xb2\xa1"
LINKTYPE_ETHERNET = 1
ETH_IPV4, ETH_ARP, ETH_VLAN = 0x0800, 0x0806, 0x8100

COLUMNS = ["packet_no", "ts_us", "length", "ethertype", "ip_proto", "src_ip", "dst_ip", "src_port", "dst_port"]


def _ipv4_str(v: int) -> str:
    return "" if v == 0 else f"{v >> 24 & 255}.{v >> 16 & 255}.{v >> 8 & 255}.{v & 255}"


def read_pcap(path: str | Path) -> pd.DataFrame:
    """One row per packet, in file order. `packet_no` is 1-based, matching Wireshark's frame.number."""
    rows = {c: [] for c in COLUMNS}
    with open(path, "rb") as f:
        header = f.read(24)
        if header[:4] != PCAP_MAGIC_LE_US:
            raise ValueError(f"{path}: not a little-endian microsecond pcap (magic {header[:4].hex()})")
        linktype = struct.unpack("<I", header[20:24])[0]
        if linktype != LINKTYPE_ETHERNET:
            raise ValueError(f"{path}: unsupported link type {linktype}")
        n = 0
        while True:
            rec = f.read(16)
            if len(rec) < 16:
                break
            ts_sec, ts_usec, incl_len, orig_len = struct.unpack("<IIII", rec)
            data = f.read(incl_len)
            n += 1
            ethertype = int.from_bytes(data[12:14], "big") if len(data) >= 14 else 0
            off = 14
            if ethertype == ETH_VLAN and len(data) >= 18:
                ethertype, off = int.from_bytes(data[16:18], "big"), 18
            proto = src = dst = sport = dport = 0
            if ethertype == ETH_IPV4 and len(data) >= off + 20:
                ihl = (data[off] & 0x0F) * 4
                proto = data[off + 9]
                src = int.from_bytes(data[off + 12:off + 16], "big")
                dst = int.from_bytes(data[off + 16:off + 20], "big")
                if proto in (6, 17) and len(data) >= off + ihl + 4:
                    sport = int.from_bytes(data[off + ihl:off + ihl + 2], "big")
                    dport = int.from_bytes(data[off + ihl + 2:off + ihl + 4], "big")
            elif ethertype == ETH_ARP and len(data) >= off + 28:
                src = int.from_bytes(data[off + 14:off + 18], "big")   # sender protocol address
                dst = int.from_bytes(data[off + 24:off + 28], "big")   # target protocol address
            rows["packet_no"].append(n)
            rows["ts_us"].append(ts_sec * 1_000_000 + ts_usec)
            rows["length"].append(orig_len)
            rows["ethertype"].append(ethertype)
            rows["ip_proto"].append(proto)
            rows["src_ip"].append(src)
            rows["dst_ip"].append(dst)
            rows["src_port"].append(sport)
            rows["dst_port"].append(dport)
    return pd.DataFrame({
        "packet_no": np.asarray(rows["packet_no"], dtype=np.int64),
        "ts_us": np.asarray(rows["ts_us"], dtype=np.int64),
        "length": np.asarray(rows["length"], dtype=np.int32),
        "ethertype": np.asarray(rows["ethertype"], dtype=np.int32),
        "ip_proto": np.asarray(rows["ip_proto"], dtype=np.int16),
        "src_ip": np.asarray(rows["src_ip"], dtype=np.uint32),
        "dst_ip": np.asarray(rows["dst_ip"], dtype=np.uint32),
        "src_port": np.asarray(rows["src_port"], dtype=np.int32),
        "dst_port": np.asarray(rows["dst_port"], dtype=np.int32),
    })


def _epoch_us(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=UTC).timestamp() * 1_000_000)


def index_capture(path: str | Path, valid_time_utc: tuple[str, str],
                  session_gap_seconds: float) -> tuple[pd.DataFrame, dict]:
    """Packet table sorted by time, with `valid_ts` and `session` columns, plus a summary."""
    df = read_pcap(path)
    lo, hi = _epoch_us(valid_time_utc[0]), _epoch_us(valid_time_utc[1])
    df["valid_ts"] = (df.ts_us >= lo) & (df.ts_us < hi)
    out_of_order = int((np.diff(df.ts_us.to_numpy()) < 0).sum())
    df = df.sort_values(["valid_ts", "ts_us", "packet_no"], ascending=[False, True, True], kind="stable")
    df = df.reset_index(drop=True)
    valid = df.valid_ts.to_numpy()
    gaps = np.diff(df.ts_us.to_numpy()[valid], prepend=df.ts_us.to_numpy()[valid][:1])
    session = np.full(len(df), -1, dtype=np.int32)
    session[valid] = np.cumsum(gaps > session_gap_seconds * 1_000_000)
    df["session"] = session
    v = df[df.valid_ts]
    summary = {
        "packets": int(len(df)),
        "invalid_timestamps": int((~df.valid_ts).sum()),
        "out_of_order_in_file": out_of_order,
        "sessions": int(v.session.max() + 1) if len(v) else 0,
        "start_utc": datetime.fromtimestamp(v.ts_us.min() / 1e6, UTC).isoformat() if len(v) else None,
        "end_utc": datetime.fromtimestamp(v.ts_us.max() / 1e6, UTC).isoformat() if len(v) else None,
        "busy_seconds": float(v.groupby("session").ts_us.agg(lambda s: (s.max() - s.min()) / 1e6).sum())
        if len(v) else 0.0,
    }
    return df, summary


def ip_to_str(values) -> list[str]:
    return [_ipv4_str(int(v)) for v in values]
