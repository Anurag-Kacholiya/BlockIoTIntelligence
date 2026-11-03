import numpy as np
import pandas as pd

from src.data.preparation.timestamps import (
    AMBIGUOUS,
    BAD_TIME,
    MATCHED,
    RESOLVED_BY_ORDER,
    UNMATCHED,
    csv_time_of_day_us,
    ip_to_int,
    match_rows,
)

H = 3_600_000_000
DAY0 = 1_640_995_200_000_000          # 2022-01-01 00:00:00 UTC in µs


def _packets(rows):
    """rows: (packet_no, utc_hour, utc_us_within_hour, src, dst)"""
    return pd.DataFrame({
        "packet_no": [r[0] for r in rows],
        "ts_us": [DAY0 + r[1] * H + r[2] for r in rows],
        "src_ip": ip_to_int(pd.Series([r[3] for r in rows])),
        "dst_ip": ip_to_int(pd.Series([r[4] for r in rows])),
    })


def test_csv_time_parsing_and_bad_values():
    tod = csv_time_of_day_us(pd.Series([" 2021 01:00:00.000005000 ", "2022 23:59:59.999999", "192.168.0.128", "6.0"]))
    assert tod.tolist() == [1 * H + 5, 23 * H + 59 * 60_000_000 + 59_999_999, -1, -1]


def test_ip_to_int_handles_non_ip_text():
    assert ip_to_int(pd.Series(["10.0.0.1", "0", "0.0", ""])).tolist() == [167772161, 0, 0, 0]


def test_unique_match_with_utc_plus_one():
    pk = _packets([(1, 0, 5, "10.0.0.1", "10.0.0.2"), (2, 0, 9, "10.0.0.1", "10.0.0.2")])
    # CSV local time is UTC+1: packet at 00:00:00.000005 UTC is written as 01:00:00.000005
    idx, st = match_rows(np.array([1 * H + 5]), np.array([0]), np.array([0]), pk, utc_offset_hours=1)
    assert idx.tolist() == [0] and st.tolist() == [MATCHED]
    idx, st = match_rows(np.array([1 * H + 5]), np.array([0]), np.array([0]), pk, utc_offset_hours=0)
    assert st.tolist() == [UNMATCHED]


def test_ip_filter_disambiguates_same_microsecond():
    pk = _packets([(1, 0, 5, "10.0.0.1", "10.0.0.2"), (2, 0, 5, "10.0.0.3", "10.0.0.4")])
    src, dst = ip_to_int(pd.Series(["10.0.0.3"])), ip_to_int(pd.Series(["10.0.0.4"]))
    idx, st = match_rows(np.array([H + 5]), src, dst, pk, 1)
    assert idx.tolist() == [1] and st.tolist() == [MATCHED]


def test_order_resolves_only_when_exactly_one_candidate_fits():
    # Same time of day on two different days (multi-day capture); neighbours pin down the right one.
    pk = _packets([(10, 0, 1, "a", "b"), (11, 0, 7, "a", "b"), (12, 0, 9, "a", "b"), (50, 24, 7, "a", "b")])
    rows = np.array([H + 1, H + 7, H + 9])
    idx, st = match_rows(rows, np.zeros(3, int), np.zeros(3, int), pk, 1)
    assert st.tolist() == [MATCHED, RESOLVED_BY_ORDER, MATCHED]
    assert pk.packet_no.to_numpy()[idx[1]] == 11


def test_unresolvable_stays_ambiguous_and_packets_are_not_shared():
    pk = _packets([(1, 0, 7, "a", "b"), (2, 24, 7, "a", "b")])        # two candidates, no neighbours
    idx, st = match_rows(np.array([H + 7]), np.zeros(1, int), np.zeros(1, int), pk, 1)
    assert st.tolist() == [AMBIGUOUS] and idx.tolist() == [-1]
    pk = _packets([(1, 0, 7, "a", "b")])                               # two rows claim one packet
    idx, st = match_rows(np.array([H + 7, H + 7]), np.zeros(2, int), np.zeros(2, int), pk, 1)
    assert st.tolist() == [AMBIGUOUS, AMBIGUOUS]


def test_bad_time_is_reported():
    pk = _packets([(1, 0, 7, "a", "b")])
    _, st = match_rows(np.array([-1]), np.zeros(1, int), np.zeros(1, int), pk, 1)
    assert st.tolist() == [BAD_TIME]
