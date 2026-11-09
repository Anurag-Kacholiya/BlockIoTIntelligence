"""Train and register the device gateway's traffic forecaster (final task 3, RQ-11; Cloud Intelligence trains it).

  BLOCKIOT_VIEW=real_time python scripts/train_forecaster.py

Writes models/real_time/device_forecaster/<model_id>.{joblib,json} and current.json.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cloud.train_forecaster import train_forecaster  # noqa: E402

if __name__ == "__main__":
    os.environ.setdefault("BLOCKIOT_VIEW", "real_time")   # stored next to the models that score the realistic replay
    meta = train_forecaster()
    print(f"registered {meta.model_id}")
