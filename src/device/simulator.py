"""Replays prepared Edge-IIoTset rows as telemetry from N logical devices (ADR Phase 1 step 1, plan step 5).

The selected views carry no usable device identity or timestamp (see configs/datasets.yaml), so both
are *derived*: rows are shuffled, assigned to logical devices at random, and stamped with Poisson
arrival times. Neither carries label information, which keeps the replay free of capture-session leakage.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from src.data.preparation.clean import TARGETS

REPLAY_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


class DeviceSimulator:
    def __init__(self, rows: pd.DataFrame, n_devices: int, seed: int, events_per_second: float = 1000.0,
                 source_file: str = ""):
        rng = np.random.default_rng(seed)
        self.rows = rows.sample(frac=1.0, random_state=seed).reset_index(drop=True)
        self.features = [c for c in rows.columns if c not in TARGETS + ["source_row_id"]]
        self.device_index = rng.integers(0, n_devices, size=len(self.rows))
        gaps = rng.exponential(1.0 / events_per_second, size=len(self.rows))
        self.offsets = np.cumsum(gaps)
        self.n_devices = n_devices
        self.source_file = source_file
        self._uuid_ns = uuid.UUID(int=seed)

    @staticmethod
    def device_id(i: int) -> str:
        return f"device-{i:04d}"

    def __len__(self) -> int:
        return len(self.rows)

    def batches(self, size: int) -> Iterator[list[dict]]:
        sequence = np.zeros(self.n_devices, dtype=np.int64)
        values = self.rows[self.features].to_dict("records")
        labels = self.rows["Attack_label"].to_numpy()
        types = self.rows["Attack_type"].to_numpy()
        row_ids = self.rows["source_row_id"].to_numpy()
        for start in range(0, len(self.rows), size):
            batch = []
            for i in range(start, min(start + size, len(self.rows))):
                d = int(self.device_index[i])
                event_id = str(uuid.uuid5(self._uuid_ns, str(i)))   # deterministic per seed
                batch.append({
                    "event_id": event_id,
                    "device_id": self.device_id(d),
                    "trace_id": event_id,
                    "timestamp": REPLAY_EPOCH + timedelta(seconds=float(self.offsets[i])),
                    "sequence_number": int(sequence[d]),
                    "values": values[i],
                    "source_file": self.source_file,
                    "source_row_id": int(row_ids[i]),
                    "attack_label": int(labels[i]),
                    "attack_type": str(types[i]),
                })
                sequence[d] += 1
            yield batch
