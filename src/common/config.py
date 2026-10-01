"""Configuration loading. Every run reads configs/*.yaml through here so the config hash can be recorded."""

from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"


@cache
def load_config(name: str) -> dict[str, Any]:
    """Load configs/<name>.yaml. Cached; treat the result as read-only."""
    path = CONFIG_DIR / f"{name}.yaml"
    with path.open() as f:
        return yaml.safe_load(f) or {}


def config_hash(*names: str) -> str:
    """SHA-256 over the parsed content of the named configs, for experiment manifests (ADR §19.1)."""
    payload = {n: load_config(n) for n in sorted(names)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def resolve(path: str | Path) -> Path:
    """Resolve a repo-relative path from a config file to an absolute path."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p
