"""Timing, resource and experiment metric collection (ADR §15, Phase 8)."""

from __future__ import annotations

import csv
import os
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import psutil

from src.common.schemas import ExperimentMetric


class LatencyTracker:
    """Collects per-stage latencies in milliseconds and summarizes them."""

    def __init__(self) -> None:
        self.samples: dict[str, list[float]] = defaultdict(list)
        self.cpu_ms: dict[str, float] = defaultdict(float)   # this process's CPU time spent in each stage

    @contextmanager
    def measure(self, stage: str):
        start, cpu_start = time.perf_counter(), time.process_time()
        try:
            yield
        finally:
            self.samples[stage].append((time.perf_counter() - start) * 1000)
            self.cpu_ms[stage] += (time.process_time() - cpu_start) * 1000

    def summary(self) -> dict[str, dict[str, float]]:
        out = {}
        for stage, xs in self.samples.items():
            a = np.asarray(xs)
            out[stage] = {
                "count": int(a.size),
                "mean_ms": float(a.mean()),
                "p50_ms": float(np.percentile(a, 50)),
                "p95_ms": float(np.percentile(a, 95)),
                "p99_ms": float(np.percentile(a, 99)),
                "total_ms": float(a.sum()),
                "cpu_total_ms": float(self.cpu_ms.get(stage, 0.0)),
            }
        return out


class ResourceSampler:
    """CPU% and RSS of this process between start() and stop()."""

    def __init__(self) -> None:
        self._proc = psutil.Process(os.getpid())

    def start(self) -> None:
        self._proc.cpu_percent(None)
        self._cpu_times = self._proc.cpu_times()
        self._wall = time.perf_counter()

    def stop(self) -> dict[str, float]:
        cpu = self._proc.cpu_times()
        wall = time.perf_counter() - self._wall
        cpu_s = (cpu.user - self._cpu_times.user) + (cpu.system - self._cpu_times.system)
        return {
            "wall_s": wall,
            "cpu_s": cpu_s,  # also the energy proxy until direct power measurement exists (ADR §10 Phase 8)
            "cpu_percent_avg": 100 * cpu_s / wall if wall else 0.0,
            "rss_mb": self._proc.memory_info().rss / 2**20,
        }


def write_metrics(metrics: list[ExperimentMetric], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(ExperimentMetric.model_fields))
        if new:
            writer.writeheader()
        for m in metrics:
            writer.writerow(m.model_dump(mode="json"))
