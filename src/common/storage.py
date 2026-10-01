"""Off-chain storage: Parquet files with SHA-256 manifests (ADR §9)."""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.config import ROOT
from src.common.crypto import hash_file


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def write_parquet(df: pd.DataFrame, path: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write df to path and a sibling <name>.manifest.json recording its hash and lineage."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    record = {
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "file_hash": hash_file(path),
        "rows": len(df),
        "columns": len(df.columns),
        "created_at": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "pandas": pd.__version__,
        **(manifest or {}),
    }
    path.with_suffix(".manifest.json").write_text(json.dumps(record, indent=2, default=str))
    return record


def read_parquet(path: Path, verify: bool = True) -> pd.DataFrame:
    """Read a file written by write_parquet, refusing it if its content no longer matches the manifest."""
    if verify:
        expected = json.loads(path.with_suffix(".manifest.json").read_text())["file_hash"]
        if hash_file(path) != expected:
            raise ValueError(f"{path} does not match its manifest hash")
    return pd.read_parquet(path)
