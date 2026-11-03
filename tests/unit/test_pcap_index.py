import struct

import pytest

from src.data.ingestion.pcap_index import index_capture, ip_to_str, read_pcap

BASE = 1_640_000_000          # 2021-12-20 UTC, inside the valid window
VALID = ("2021-01-01T00:00:00", "2023-01-01T00:00:00")


def _eth(ethertype: int) -> bytes:
    return b"\xaa" * 6 + b"\xbb" * 6 + ethertype.to_bytes(2, "big")


def _ipv4(src: str, dst: str, proto: int, payload: bytes) -> bytes:
    hdr = bytes([0x45, 0, 0, 20 + len(payload), 0, 0, 0, 0, 64, proto, 0, 0])
    hdr += bytes(map(int, src.split("."))) + bytes(map(int, dst.split(".")))
    return hdr + payload


def _udp(sport: int, dport: int) -> bytes:
    return sport.to_bytes(2, "big") + dport.to_bytes(2, "big") + b"\x00\x08\x00\x00"


def _arp(sender: str, target: str) -> bytes:
    return (b"\x00\x01\x08\x00\x06\x04\x00\x01" + b"\xbb" * 6 + bytes(map(int, sender.split(".")))
            + b"\x00" * 6 + bytes(map(int, target.split("."))))


def _pcap(path, packets):
    with open(path, "wb") as f:
        f.write(b"\xd4\xc3\xb2\xa1" + struct.pack("<HHiIII", 2, 4, 0, 0, 65535, 1))
        for sec, usec, data in packets:
            f.write(struct.pack("<IIII", sec, usec, len(data), len(data)) + data)


@pytest.fixture
def capture(tmp_path):
    p = tmp_path / "t.pcap"
    _pcap(p, [
        (BASE, 500, _eth(0x0800) + _ipv4("192.168.3.18", "192.168.3.12", 17, _udp(5353, 53))),
        (BASE, 100, _eth(0x0806) + _arp("192.168.0.101", "192.168.0.1")),          # out of order (earlier)
        (BASE + 10, 0, _eth(0x0800) + _ipv4("10.0.0.1", "10.0.0.2", 6, b"\x04\xd2\x07\x5b" + b"\x00" * 16)),
        (BASE + 7200, 0, _eth(0x0800) + _ipv4("10.0.0.1", "10.0.0.2", 1, b"")),     # 2 h later: new session
        (3_000_000_000, 0, _eth(0x0800) + _ipv4("10.0.0.1", "10.0.0.2", 1, b"")),   # year 2065: corrupt
    ])
    return p


def test_read_pcap_parses_ipv4_ports_and_arp(capture):
    df = read_pcap(capture)
    assert df.packet_no.tolist() == [1, 2, 3, 4, 5]
    assert ip_to_str(df.src_ip[:3]) == ["192.168.3.18", "192.168.0.101", "10.0.0.1"]
    assert (df.ip_proto[0], df.src_port[0], df.dst_port[0]) == (17, 5353, 53)
    assert df.ethertype[1] == 0x0806 and ip_to_str([df.dst_ip[1]]) == ["192.168.0.1"]
    assert (df.src_port[2], df.dst_port[2]) == (1234, 1883)


def test_index_sorts_flags_corrupt_time_and_splits_sessions(capture):
    df, summary = index_capture(capture, VALID, session_gap_seconds=3600)
    assert summary["invalid_timestamps"] == 1 and summary["out_of_order_in_file"] == 1
    valid = df[df.valid_ts]
    assert valid.ts_us.is_monotonic_increasing
    assert valid.packet_no.tolist() == [2, 1, 3, 4]
    assert valid.session.tolist() == [0, 0, 0, 1]
    assert summary["sessions"] == 2
    assert df[~df.valid_ts].session.tolist() == [-1]


def test_rejects_unsupported_format(tmp_path):
    p = tmp_path / "x.pcap"
    p.write_bytes(b"\x0a\x0d\x0d\x0a" + b"\x00" * 40)   # pcapng magic
    with pytest.raises(ValueError):
        read_pcap(p)
