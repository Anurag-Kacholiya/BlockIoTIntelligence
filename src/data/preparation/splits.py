"""Leakage-safe stratified train/validation/test split (dataset plan step 8)."""

from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split

from src.common.config import load_config
from src.data.preparation.clean import feature_columns


def split(df: pd.DataFrame, seed: int | None = None) -> dict[str, pd.DataFrame]:
    cfg = load_config("datasets")["edge_iiotset"]["split"]
    seed = cfg["seed"] if seed is None else seed
    strat = cfg["stratify_on"]
    holdout = cfg["validation"] + cfg["test"]
    train, rest = train_test_split(df, test_size=holdout, stratify=df[strat], random_state=seed)
    validation, test = train_test_split(
        rest, test_size=cfg["test"] / holdout, stratify=rest[strat], random_state=seed
    )
    return {"train": train, "validation": validation, "test": test}


def cross_split_overlap(parts: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Rows in validation/test whose feature vector also occurs in train (only label-conflict rows
    can remain after exact de-duplication). Reported so the evaluation can state the exposure."""
    cols = feature_columns(parts["train"])
    train_keys = set(pd.util.hash_pandas_object(parts["train"][cols], index=False))
    return {
        name: int(pd.util.hash_pandas_object(parts[name][cols], index=False).isin(train_keys).sum())
        for name in ("validation", "test")
    }
