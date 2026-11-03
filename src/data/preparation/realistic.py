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
