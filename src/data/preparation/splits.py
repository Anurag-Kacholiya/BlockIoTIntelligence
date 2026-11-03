"""Leakage-safe splits (dataset plan step 8; final task 1 step 7).

A. `split`: random stratified 70/15/15 (the mid-term protocol).
B. `time_split`: the earliest 70% of every capture session trains, the next 15% validates, the latest 15% tests.
C. `leave_one_device_out`: one sensor's normal traffic is never seen in training.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from src.common.config import load_config
from src.data.preparation.clean import feature_columns

PARTITIONS = ("train", "validation", "test")
SESSION_KEY = ["capture", "session"]


def split(df: pd.DataFrame, seed: int | None = None, stratify: str | list[str] | None = None,
          ) -> dict[str, pd.DataFrame]:
    cfg = load_config("datasets")["edge_iiotset"]["split"]
    seed = cfg["seed"] if seed is None else seed
    # Sorted group numbers keep the class order of np.unique, so the mid-term split is reproduced exactly.
    strat = df.groupby(stratify or cfg["stratify_on"], sort=True).ngroup()
    holdout = cfg["validation"] + cfg["test"]
    train, rest = train_test_split(df, test_size=holdout, stratify=strat, random_state=seed)
    validation, test = train_test_split(
        rest, test_size=cfg["test"] / holdout, stratify=strat.loc[rest.index], random_state=seed
    )
    return {"train": train, "validation": validation, "test": test}


def session_cuts(meta: pd.DataFrame) -> pd.DataFrame:
    """Per capture session: the timestamps where validation and test begin (at 70% and 85% of its rows in time order).

    Computed once on a session's full traffic, so de-duplication and sampling cannot move a boundary, and the
    realistic replay streams exactly the test window. Rows stamped exactly at a cut belong to the later part.
    """
    cfg = load_config("datasets")["edge_iiotset"]["split"]
    records = []
    for (capture, session), ts in meta.groupby(SESSION_KEY, sort=True).ts_us:
        ts = np.sort(ts.to_numpy())
        records.append({
            "capture": capture, "session": int(session), "rows": len(ts), "start_us": int(ts[0]),
            "end_us": int(ts[-1]), "validation_start_us": _ts_at(ts, cfg["train"]),
            "test_start_us": _ts_at(ts, cfg["train"] + cfg["validation"]),
        })
    return pd.DataFrame(records)


def _ts_at(sorted_ts: np.ndarray, fraction: float) -> int:
    k = int(len(sorted_ts) * fraction)
    return int(sorted_ts[k]) if k < len(sorted_ts) else int(sorted_ts[-1]) + 1


def time_partition(df: pd.DataFrame, cuts: pd.DataFrame) -> np.ndarray:
    """'train' / 'validation' / 'test' for every row, from its session's cut timestamps."""
    m = df[SESSION_KEY].merge(cuts, on=SESSION_KEY, how="left", validate="many_to_one")
    if m.test_start_us.isna().any():
        raise ValueError("rows from a session without cut points")
    ts = df.ts_us.to_numpy()
    return np.where(ts >= m.test_start_us.to_numpy(), "test",
                    np.where(ts >= m.validation_start_us.to_numpy(), "validation", "train"))


def time_split(df: pd.DataFrame, cuts: pd.DataFrame) -> dict[str, pd.DataFrame]:
    part = time_partition(df, cuts)
    return {name: df[part == name] for name in PARTITIONS}


def leave_one_device_out(df: pd.DataFrame, cuts: pd.DataFrame, device: str) -> dict[str, pd.DataFrame]:
    """Train/validation: the time-split train/validation rows, minus all of `device`'s normal traffic.
    Test: all of `device`'s normal traffic (unseen) plus every other row's time-split test part, so the same
    models also report seen devices and attacks. Attacks are split by time, since they are not per sensor."""
    held = ((df.Attack_label == 0) & (df.device_id == device)).to_numpy()
    if not held.any():
        raise ValueError(f"no normal traffic for device {device!r}")
    part = time_partition(df, cuts)
    return {
        "train": df[(part == "train") & ~held],
        "validation": df[(part == "validation") & ~held],
        "test": df[(part == "test") | held],
    }


def cross_split_overlap(parts: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Rows in validation/test whose feature vector also occurs in train (only label-conflict rows
    can remain after exact de-duplication). Reported so the evaluation can state the exposure."""
    cols = feature_columns(parts["train"])
    train_keys = set(pd.util.hash_pandas_object(parts["train"][cols], index=False))
    return {
        name: int(pd.util.hash_pandas_object(parts[name][cols], index=False).isin(train_keys).sum())
        for name in ("validation", "test")
    }
