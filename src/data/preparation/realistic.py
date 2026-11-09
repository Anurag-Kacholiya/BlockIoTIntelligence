"""Access to the realistic event tables built by scripts/build_realistic_events.py (final task 1).

Dataset v2 and the realistic replay both read events through `read_events`, so they apply the same row rule:
every packet of a normal capture (all of it is normal sensor traffic), but only the publisher's selected packets
of an attack capture. The publisher left out mostly UDP background (DNS, mDNS, SSDP, broadcasts) and IPv6; in an
attack capture that background is not attack traffic, so its label is unknown and it is not used.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from src.common.config import load_config, resolve

ROW_ID_STRIDE = 100_000_000   # > packets in any capture (largest: 3.5 M)


def captures() -> dict[str, dict]:
    return load_config("datasets")["realistic"]["captures"]


def source_row_ids(capture: str, packet_no: pd.Series) -> pd.Series:
    """Stable row id across dataset v2 and the replay: capture position in the config, then frame number."""
    if packet_no.max() >= ROW_ID_STRIDE:
        raise ValueError("packet number exceeds the row-id stride")
    return list(captures()).index(capture) * ROW_ID_STRIDE + packet_no.astype("int64")


def share_budget(sizes: dict[str, int], total: int | None) -> dict[str, int]:
    """Split `total` rows equally over captures; a capture with fewer rows passes its unused share to the others.
    The result sums to min(total, all rows), and is deterministic (any remainder goes to the smaller captures)."""
    if total is None or total >= sum(sizes.values()):
        return dict(sizes)
    budget, left, open_ = {}, total, sorted(sizes, key=lambda c: (sizes[c], c))
    while open_:
        share = left // len(open_)
        if sizes[open_[0]] <= share:
            c = open_.pop(0)
            budget[c] = sizes[c]
            left -= sizes[c]
            continue
        extra = left - share * len(open_)
        budget |= {c: share + (i < extra) for i, c in enumerate(open_)}
        break
    return budget


def events_path(capture: str) -> Path:
    return resolve(load_config("datasets")["realistic"]["paths"]["events"]) / f"{capture}.parquet"


def read_events(capture: str, columns: list[str] | None = None, filters: list | None = None) -> pd.DataFrame:
    """A capture's labelled packets in time order. `filters` is a pyarrow filter (AND list, or OR of AND lists)."""
    if captures()[capture]["kind"] == "attack":
        selected = ("publisher_selected", "=", True)
        if not filters:
            filters = [selected]
        elif isinstance(filters[0], list):
            filters = [[*conj, selected] for conj in filters]
        else:
            filters = [*filters, selected]
    df = pq.read_table(events_path(capture), columns=columns, filters=filters or None).to_pandas()
    if "ts_us" in df.columns and not df.ts_us.is_monotonic_increasing:
        df = df.sort_values([c for c in ("ts_us", "packet_no") if c in df.columns], kind="stable", ignore_index=True)
    return df


WINDOWS = {"train": ("start_us", "validation_start_us"), "validation": ("validation_start_us", "test_start_us"),
           "test": ("test_start_us", None)}
TIMING_COLUMNS = ["capture", "device_id", "session", "ts_us", "packet_no", "Attack_label"]


def window_packets(capture: str, window: str, cuts: pd.DataFrame) -> pd.DataFrame:
    """A capture's labelled packets in one time-split window (train / validation / test), timing columns only, with
    `offset_us` = time since its session's window start (sessions overlaid, as the realistic replay does), sorted."""
    lo, hi = WINDOWS[window]
    filters = [[("session", "=", int(c.session)), ("ts_us", ">=", int(getattr(c, lo))),
                *([("ts_us", "<", int(getattr(c, hi)))] if hi else [])]
               for c in cuts[cuts.capture == capture].itertuples()]
    w = read_events(capture, columns=TIMING_COLUMNS, filters=filters)
    w["offset_us"] = w.ts_us - w.groupby("session").ts_us.transform("min")
    return w.sort_values(["offset_us", "packet_no"], kind="stable", ignore_index=True)


def timing_stream(packets: dict[str, pd.DataFrame], n_rows: int | None, rng=None) -> pd.DataFrame:
    """The realistic replay's construction (pipeline.load_replay_rows) on any window, timing columns only: every
    capture an equal share of `n_rows` as one contiguous slice. rng=None starts every slice at the window start (on
    the test window: exactly the replayed messages); with a numpy Generator each capture's slice starts at a random
    packet of its window, for training and validation streams. Feed the result to RealtimeReplay."""
    budget = share_budget({c: len(w) for c, w in packets.items()}, n_rows)
    parts = []
    for capture, b in budget.items():
        if b == 0:
            continue
        w = packets[capture]
        start = 0 if rng is None else int(rng.integers(0, len(w) - b + 1))
        parts.append(w.iloc[start:start + b])
    return pd.concat(parts, ignore_index=True).drop(columns="offset_us")
