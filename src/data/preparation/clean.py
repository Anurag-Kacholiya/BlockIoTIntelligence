"""Cleaning and leakage removal (dataset plan steps 2-3).

Mirrors the publisher's preprocessing (Readme.txt, steps 4-5) and records a reason for every
removed column and row so the report's feature-removal table is generated, not hand-written.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.common.config import load_config

TARGETS = ["Attack_label", "Attack_type"]
PROVENANCE = ["source_row_id"]

# Absent-value placeholders appear as both "0" and "0.0" in the categorical columns.
_ZERO = {"0", "0.0", ""}


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in TARGETS + PROVENANCE]


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict], dict]:
    """Return (clean_df, column_removals, row_report)."""
    cfg = load_config("datasets")["edge_iiotset"]
    removals: list[dict] = []

    leak = [c for c in cfg["leakage_drop_columns"] if c in df.columns]
    removals += [
        {"column": c, "reason": "publisher drop list: identifier/timestamp/port/free-text payload (leakage)"}
        for c in leak
    ]
    df = df.drop(columns=leak)

    categorical = [c for c in cfg["categorical_columns"] if c in df.columns]
    for c in categorical:
        df[c] = df[c].str.strip().where(~df[c].str.strip().isin(_ZERO), "0")

    numeric = [c for c in feature_columns(df) if c not in categorical]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["Attack_label"] = df["Attack_label"].astype(float).astype(int)

    constant = [c for c in feature_columns(df) if df[c].nunique(dropna=False) <= 1]
    removals += [{"column": c, "reason": "constant across the whole file (no information)"} for c in constant]
    df = df.drop(columns=constant)

    report = {"rows_in": len(df)}
    numeric = [c for c in numeric if c not in constant]
    df[numeric] = df[numeric].replace([np.inf, -np.inf], np.nan)
    bad = df[numeric].isna().any(axis=1)
    report["rows_dropped_unparseable_or_inf"] = int(bad.sum())
    df = df[~bad]

    # Exact duplicates over features + targets carry no new information and inflate test scores.
    dup = df.duplicated(subset=feature_columns(df) + TARGETS)
    report["rows_dropped_duplicate"] = int(dup.sum())
    df = df[~dup]

    # Identical feature vectors with different labels cannot be separated by any model; keep and report.
    classes_per_vector = df.groupby(feature_columns(df), dropna=False)["Attack_type"].transform("nunique")
    report["rows_with_label_conflict"] = int((classes_per_vector > 1).sum())
    report["rows_out"] = len(df)
    report["categorical_columns"] = [c for c in categorical if c in df.columns]
    report["numeric_columns"] = numeric
    return df.reset_index(drop=True), removals, report
