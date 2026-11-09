"""Recover real timestamps for CSV rows by matching each row to its packet (final task 1, step 3).

The CSVs kept `frame.time` as "<year> HH:MM:SS.fffffffff" in local time (UTC+1); the date was lost. A row is
matched to a packet of the same capture whose local time of day is identical to the microsecond and, when the
row has IPv4 addresses, whose source and destination match too.

Rules (no guessing):
  - exactly one candidate                          -> matched
  - several candidates, but exactly one lies between the packets matched by the neighbouring rows
    (CSV rows are written in capture order)          -> matched ("resolved_by_order")
  - otherwise                                       -> ambiguous (left unmatched)
  - no candidate / unparseable time                 -> unmatched
  - a packet claimed by more than one row           -> all those rows marked ambiguous
"""

from __future__ import annotations

import ipaddress

import numpy as np
import pandas as pd

DAY_US = 86_400_000_000

MATCHED, RESOLVED_BY_ORDER, AMBIGUOUS, UNMATCHED, BAD_TIME = 0, 1, 2, 3, 4
STATUS_NAMES = {MATCHED: "matched", RESOLVED_BY_ORDER: "resolved_by_order", AMBIGUOUS: "ambiguous",
                UNMATCHED: "unmatched", BAD_TIME: "bad_time"}


def csv_time_of_day_us(frame_time: pd.Series) -> np.ndarray:
    """'<year> HH:MM:SS.fffffffff' -> microseconds since local midnight; -1 where the text is not a time."""
    t = frame_time.astype(str).str.strip()
    ok = t.str.match(r"^\d{4} \d{2}:\d{2}:\d{2}\.\d{6,9}$")
    clock = t.str.split(" ").str[-1]
    hh = pd.to_numeric(clock.str[0:2], errors="coerce")
    mm = pd.to_numeric(clock.str[3:5], errors="coerce")
    ss = pd.to_numeric(clock.str[6:8], errors="coerce")
    us = pd.to_numeric(clock.str[9:15], errors="coerce")
    tod = ((hh * 3600 + mm * 60 + ss) * 1_000_000 + us).where(ok)
    return tod.fillna(-1).astype(np.int64).to_numpy()


def ip_to_int(values: pd.Series) -> np.ndarray:
    """IPv4 text -> uint32 as int64; 0 for anything that is not an IPv4 address (e.g. "0", "0.0")."""
    out = np.zeros(len(values), dtype=np.int64)
    for i, v in enumerate(values.astype(str)):
        v = v.strip()
        if v.count(".") == 3:
            try:
                out[i] = int(ipaddress.IPv4Address(v))
            except ValueError:
                pass
    return out


def match_rows(row_tod_us: np.ndarray, row_src: np.ndarray, row_dst: np.ndarray, packets: pd.DataFrame,
               utc_offset_hours: float) -> tuple[np.ndarray, np.ndarray]:
    """Return (packet index into `packets` or -1, status code) for every CSV row.

    `packets` must contain ts_us, src_ip, dst_ip, packet_no (from pcap_index) and only valid timestamps.
    """
    n = len(row_tod_us)
    pkt_tod = (packets.ts_us.to_numpy() + int(utc_offset_hours * 3_600_000_000)) % DAY_US
    order = np.argsort(pkt_tod, kind="stable")
    tod_sorted = pkt_tod[order]
    p_src = packets.src_ip.to_numpy(dtype=np.int64)
    p_dst = packets.dst_ip.to_numpy(dtype=np.int64)
    p_no = packets.packet_no.to_numpy()

    lo = np.searchsorted(tod_sorted, row_tod_us, "left")
    hi = np.searchsorted(tod_sorted, row_tod_us, "right")
    match = np.full(n, -1, dtype=np.int64)
    status = np.full(n, UNMATCHED, dtype=np.int8)
    status[row_tod_us < 0] = BAD_TIME
    candidates: dict[int, np.ndarray] = {}

    has_ip = (row_src > 0) & (row_dst > 0)
    for i in np.flatnonzero((hi > lo) & (row_tod_us >= 0)):
        cand = order[lo[i]:hi[i]]
        if has_ip[i]:
            cand = cand[(p_src[cand] == row_src[i]) & (p_dst[cand] == row_dst[i])]
        if len(cand) == 1:
            match[i], status[i] = cand[0], MATCHED
        elif len(cand) > 1:
            status[i] = AMBIGUOUS
            candidates[i] = cand

    # Resolve ambiguities with capture order: the packet must lie between the neighbours' packets.
    if candidates:
        matched_idx = np.flatnonzero(match >= 0)
        matched_no = p_no[match[matched_idx]]
        for i, cand in candidates.items():
            k = np.searchsorted(matched_idx, i)
            prev_no = matched_no[k - 1] if k > 0 else -np.inf
            next_no = matched_no[k] if k < len(matched_idx) else np.inf
            fit = cand[(p_no[cand] > prev_no) & (p_no[cand] < next_no)]
            if len(fit) == 1:
                match[i], status[i] = fit[0], RESOLVED_BY_ORDER

    # One packet, one row.
    taken = match[match >= 0]
    uniq, counts = np.unique(taken, return_counts=True)
    dup = set(uniq[counts > 1].tolist())
    if dup:
        clash = np.isin(match, list(dup))
        match[clash] = -1
        status[clash] = AMBIGUOUS
    return match, status


def status_report(status: np.ndarray) -> dict[str, int]:
    return {STATUS_NAMES[k]: int((status == k).sum()) for k in STATUS_NAMES}
