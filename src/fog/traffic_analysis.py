"""Windowed per-device traffic statistics on replay time (ADR §7.5, plan step 7).

These are operational features for flood/replay detection and alerting. They are deliberately NOT
inputs to the multiclass classifier: replay time is derived, so any class signal in it would be an
artefact of the simulator rather than of the dataset.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime


class TrafficAnalyzer:
    def __init__(self, windows_seconds: list[int], flood_events_per_second: float):
        self.windows = sorted(windows_seconds)
        self.flood_eps = flood_events_per_second
        # One sliding deque per (device, window): amortized O(1) per event instead of rescanning history.
        self.history: dict[str, dict[int, deque[float]]] = defaultdict(lambda: {w: deque() for w in self.windows})
        self.last_seen: dict[str, float] = {}

    def observe(self, device_id: str, ts: datetime) -> dict[str, float]:
        t = ts.timestamp()
        stats = {}
        for w, q in self.history[device_id].items():
            q.append(t)
            while t - q[0] > w:
                q.popleft()
            stats[f"events_{w}s"] = float(len(q))
            stats[f"rate_{w}s"] = len(q) / w
        if device_id in self.last_seen:
            stats["last_interarrival_s"] = t - self.last_seen[device_id]
        self.last_seen[device_id] = t
        return stats

    def is_flooding(self, stats: dict[str, float]) -> bool:
        return stats[f"rate_{self.windows[0]}s"] > self.flood_eps
