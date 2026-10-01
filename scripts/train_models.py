"""Train and register the device, edge, fog and cloud models (Cloud Intelligence, ADR Phase 1/6).

  python scripts/train_models.py [--seed 42]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cloud.train import train_all  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    train_all(parser.parse_args().seed)
