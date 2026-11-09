"""Replays prepared Edge-IIoTset rows as device telemetry (ADR Phase 1 step 1, plan step 5; final task 1 step 6).

Two modes, one event format:
- `DeviceSimulator` (mid-term): the selected views carry no usable device identity or timestamp (see
  configs/datasets.yaml), so both are *derived*: rows are shuffled, assigned to N logical devices at random,
  and stamped with Poisson arrival times. Neither carries label information.
- `RealtimeReplay` (dataset v2): every row keeps its real device and its real inter-arrival time.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from src.data.preparation.clean import feature_columns

REPLAY_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


class _Replay:
    """Subclasses set rows (in send order), device_of (device id per row) and offsets (seconds after REPLAY_EPOCH)."""

    rows: pd.DataFrame
    device_of: np.ndarray
    offsets: np.ndarray
    source_file: str
    _uuid_ns: uuid.UUID

    def __len__(self) -> int:
        return len(self.rows)

    @property
    def device_ids(self) -> list[str]:
        raise NotImplementedError

    def batches(self, size: int) -> Iterator[list[dict]]:
        sequence: dict[str, int] = dict.fromkeys(self.device_ids, 0)
        values = self.rows[feature_columns(self.rows)].to_dict("records")
        labels = self.rows["Attack_label"].to_numpy()
        types = self.rows["Attack_type"].to_numpy()
        row_ids = self.rows["source_row_id"].to_numpy()
        for start in range(0, len(self.rows), size):
            batch = []
            for i in range(start, min(start + size, len(self.rows))):
                d = str(self.device_of[i])
                event_id = str(uuid.uuid5(self._uuid_ns, str(i)))   # deterministic per seed
                batch.append({
                    "event_id": event_id,
                    "device_id": d,
                    "trace_id": event_id,
                    "timestamp": REPLAY_EPOCH + timedelta(seconds=float(self.offsets[i])),
                    "sequence_number": sequence[d],
                    "values": values[i],
                    "source_file": self.source_file,
                    "source_row_id": int(row_ids[i]),
                    "attack_label": int(labels[i]),
                    "attack_type": str(types[i]),
                })
                sequence[d] += 1
            yield batch


class DeviceSimulator(_Replay):
    def __init__(self, rows: pd.DataFrame, n_devices: int, seed: int, events_per_second: float = 1000.0,
                 source_file: str = ""):
        rng = np.random.default_rng(seed)
        self.rows = rows.sample(frac=1.0, random_state=seed).reset_index(drop=True)
        self.features = feature_columns(rows)
        self.device_index = rng.integers(0, n_devices, size=len(self.rows))
        self.device_of = np.array([self.device_id(i) for i in range(n_devices)])[self.device_index]
        gaps = rng.exponential(1.0 / events_per_second, size=len(self.rows))
        self.offsets = np.cumsum(gaps)
        self.n_devices = n_devices
        self.source_file = source_file
        self._uuid_ns = uuid.UUID(int=seed)

    @staticmethod
    def device_id(i: int) -> str:
        return f"device-{i:04d}"

    @property
    def device_ids(self) -> list[str]:
        return [self.device_id(i) for i in range(self.n_devices)]


class RealtimeReplay(_Replay):
    """Rows sent by their real devices with their real inter-arrival times.

    Each capture session is shifted to start at replay time 0 and the sessions are interleaved, so real gaps,
    bursts and per-device rates are kept while the absolute capture dates (one per class, so they would reveal
    the label) are never visible. `speed` divides every gap (10 = ten times faster than real time). `limit` keeps
    the first N events in replay time: a contiguous window, so the kept events still have their real gaps.
    `replicas` > 1 splits each real device's stream round-robin over that many devices of the same type
    (`<device>#000`, `<device>#001`, ...): the device count grows while the messages and their timing stay the same
    (device-scaling experiment).
    """

    def __init__(self, rows: pd.DataFrame, speed: float = 1.0, seed: int = 0, source_file: str = "",
                 limit: int | None = None, replicas: int = 1):
        if speed <= 0:
            raise ValueError("speed must be positive")
        if replicas < 1:
            raise ValueError("replicas must be at least 1")
        start = rows.groupby(["capture", "session"]).ts_us.transform("min")
        offset_us = (rows.ts_us - start).to_numpy(dtype=np.int64)
        order = np.lexsort((rows.packet_no.to_numpy(), pd.factorize(rows.capture, sort=True)[0], offset_us))[:limit]
        self.rows = rows.iloc[order].reset_index(drop=True)
        self.features = feature_columns(rows)
        self.device_of = self.rows.device_id.to_numpy(dtype=str)
        if replicas > 1:
            nth = self.rows.groupby("device_id").cumcount().to_numpy() % replicas
            self.device_of = np.array([f"{d}#{r:03d}" for d, r in zip(self.device_of, nth, strict=True)])
        self.offsets = offset_us[order] / 1e6 / speed
        self.speed = speed
        self.source_file = source_file
        self._uuid_ns = uuid.UUID(int=seed)

    @property
    def device_ids(self) -> list[str]:
        return sorted(set(self.device_of.tolist()))
