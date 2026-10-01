"""Load an Edge-IIoTset release file with provenance columns attached (dataset plan steps 1 and 5)."""

from __future__ import annotations

import pandas as pd

from src.common.config import load_config, resolve
from src.common.crypto import hash_file


def source_path(view: str):
    cfg = load_config("datasets")["edge_iiotset"]
    return resolve(cfg["raw_dir"]) / cfg["files"][view]


def load(view: str | None = None, nrows: int | None = None) -> tuple[pd.DataFrame, dict]:
    """Return the raw rows of the ML or DNN selected view and a provenance dict.

    Every column is read as a string so that nothing is silently coerced before validation;
    typing happens in preparation.clean. `source_row_id` is the 0-based data row in the CSV.
    """
    cfg = load_config("datasets")["edge_iiotset"]
    view = view or cfg["primary"]
    path = source_path(view)
    if not path.exists():
        raise FileNotFoundError(f"{path} missing — run `make data-essential` first")
    df = pd.read_csv(path, dtype=str, keep_default_na=False, nrows=nrows)
    df.insert(0, "source_row_id", range(len(df)))
    provenance = {
        "source_dataset": "Edge-IIoTset",
        "doi": cfg["source_of_record"]["doi"],
        "mirror": cfg["download_mirror"],
        "view": view,
        "source_file": cfg["files"][view],
        "source_hash": hash_file(path),
        "raw_rows": len(df),
        "raw_columns": len(df.columns) - 1,
    }
    return df, provenance
