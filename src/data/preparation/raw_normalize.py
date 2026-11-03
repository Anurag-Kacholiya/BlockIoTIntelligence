"""Bring raw Edge-IIoTset rows (raw CSVs or tshark output) to the selected file's value encoding (final task 1, step 2).

The raw per-capture CSVs and tshark write some numeric fields as hexadecimal text (`tcp.flags` = `0x00000012`,
`tcp.checksum` = `0x0000bb14`, MQTT flag fields); the publisher's selected file stores them as decimals
(`18.0`, `47892.0`). tshark 4.x also prints boolean fields as True/False where the publisher wrote 1/0.
Verified on matched packets: after this decoding, every value agrees with the publisher's CSV.
Categorical columns keep their text (the selected file keeps e.g. `mqtt.conack.flags` = `0x00000000`), with the
absent-value spellings "", "0" and "0.0" merged to "0", exactly as `preparation.clean` does.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.common.config import load_config
from src.data.validation.schema import EXPECTED_COLUMNS

TARGETS = ["Attack_label", "Attack_type"]
ABSENT = {"", "0", "0.0"}


def feature_columns() -> list[str]:
    """The 61 publisher features, in file order (no targets)."""
    return [c for c in EXPECTED_COLUMNS if c not in TARGETS]


def decode_numeric(values: pd.Series, empty_as_zero: bool) -> pd.Series:
    """Parse a text column to float: hex ("0x…") decoded, decimals parsed, anything else NaN.

    `empty_as_zero`: tshark writes "" for a field the packet does not have; the publisher's CSVs write 0.
    """
    v = values.astype(str).str.strip()
    v = v.replace({"True": "1", "False": "0"})   # tshark 4.x prints booleans as words; the publisher wrote 1/0
    out = pd.to_numeric(v, errors="coerce")
    is_hex = v.str.startswith(("0x", "0X"))
    if is_hex.any():
        out.loc[is_hex] = v[is_hex].map(lambda x: float(int(x, 16)) if _is_hex(x) else np.nan)
    if empty_as_zero:
        out.loc[v.eq("")] = 0.0
    return out.astype(float)


def _is_hex(x: str) -> bool:
    try:
        int(x, 16)
        return True
    except ValueError:
        return False


def normalize_categorical(values: pd.Series) -> pd.Series:
    v = values.astype(str).str.strip()
    return v.where(~v.isin(ABSENT), "0")


def schema(name: str) -> tuple[set[str], list[str]]:
    """(columns to drop, categorical columns) for the "selected" (mid-term) or "realistic" (final) encoding."""
    cfg = load_config("datasets")
    drop = set(cfg["edge_iiotset"]["leakage_drop_columns"])
    if name == "selected":
        return drop, list(cfg["edge_iiotset"]["categorical_columns"])
    if name == "realistic":
        fs = cfg["realistic"]["feature_schema"]
        return drop | set(fs["extra_drop_columns"]), list(fs["categorical_columns"])
    raise ValueError(name)


def normalize(raw: pd.DataFrame, empty_as_zero: bool = False,
              schema_name: str = "realistic") -> tuple[pd.DataFrame, pd.Series]:
    """Return (model features in the chosen encoding, per-row validity mask).

    Leakage columns are not returned (the caller keeps what it needs as metadata). A row is invalid if any
    numeric feature cannot be parsed, which is also how misaligned publisher rows show up.
    """
    drop, categorical = schema(schema_name)
    out = pd.DataFrame(index=raw.index)
    for c in feature_columns():
        if c in drop:
            continue
        out[c] = normalize_categorical(raw[c]) if c in categorical else decode_numeric(raw[c], empty_as_zero)
    numeric = [c for c in out.columns if c not in categorical]
    valid = out[numeric].notna().all(axis=1) & np.isfinite(out[numeric]).all(axis=1)
    return out, valid
