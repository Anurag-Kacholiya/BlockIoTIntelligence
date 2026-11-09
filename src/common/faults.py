"""Fault injection for the fault-tolerance experiment (add-on after final task 2; ADR Experiment F).

A schedule of faults, each taking one component down at `down_at_s` and repairing it at `up_at_s` (seconds after the
stream starts; None: repaired when the stream ends). Targets:
  device:<id>          the device sends nothing while it is down (its readings in that window are never sent)
  edge-<k>, fog-<k>,   the component is unreachable while down; what happens to the traffic meant for it is the
  cloud                run's policy (see pipeline._stream_with_faults)
  node:<i>             blockchain validator i crashes (SIGKILL) and is later restarted with its own key and data

The schedule runs in its own thread: while a chain has lost its quorum, the pipeline thread is blocked inside a
transaction, and the repair must still happen on time. Every action is logged with its time.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import asdict, dataclass

TARGET = re.compile(r"^(device:.+|edge-\d+|fog-\d+|cloud|node:\d+)$")


@dataclass(frozen=True)
class Fault:
    target: str
    down_at_s: float
    up_at_s: float | None = None

    def __post_init__(self):
        if not TARGET.match(self.target):
            raise ValueError(f"unknown fault target {self.target!r}")
        if self.up_at_s is not None and self.up_at_s <= self.down_at_s:
            raise ValueError(f"{self.target}: repaired at {self.up_at_s} s, before it fails at {self.down_at_s} s")

    @property
    def node(self) -> int | None:
        return int(self.target.removeprefix("node:")) if self.target.startswith("node:") else None


class FaultInjector:
    """Applies a fault schedule during a run. `snapshot()` is what the pipeline sees as down; node faults act on a
    `src.common.qbft.Network` (stop/start/head)."""

    def __init__(self, faults: list[Fault], network=None, resync_timeout_s: float = 600):
        if any(f.node is not None for f in faults) and network is None:
            raise ValueError("node faults need a multi-node network (chain_backend='qbft')")
        targets = [f.target for f in faults]
        if len(set(targets)) != len(targets):
            raise ValueError("one fault per target")
        self.faults, self.network, self.resync_timeout_s = list(faults), network, resync_timeout_s
        self.log: list[dict] = []
        self._down: set[str] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._resyncs: list[threading.Thread] = []
        self._thread: threading.Thread | None = None
        self.t0 = self.epoch0 = None

    def start(self) -> None:
        self.t0, self.epoch0 = time.perf_counter(), time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def now(self) -> float:
        return time.perf_counter() - self.t0

    def snapshot(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._down)

    def _note(self, target: str, action: str, **detail) -> None:
        with self._lock:
            self.log.append({"t_s": round(self.now(), 3), "target": target, "action": action, **detail})

    def _run(self) -> None:
        actions = [(f.down_at_s, 0, f, "down") for f in self.faults]
        actions += [(f.up_at_s, 1, f, "up") for f in self.faults if f.up_at_s is not None]
        for at, _, fault, action in sorted(actions, key=lambda a: (a[0], a[1], a[2].target)):
            if self._stop.wait(max(0.0, at - self.now())):
                return                                 # the stream ended first
            self._apply(fault, action)

    def _apply(self, fault: Fault, action: str, **detail) -> None:
        if fault.node is not None:
            (self.network.stop if action == "down" else self.network.start)(fault.node)
        with self._lock:
            (self._down.add if action == "down" else self._down.discard)(fault.target)
        self._note(fault.target, action, **detail)
        if fault.node is not None and action == "up":   # logged after the restart itself
            t = threading.Thread(target=self._resync, args=(fault.node, self.now()), daemon=True)
            self._resyncs.append(t)
            t.start()

    def _resync(self, i: int, restarted_at: float) -> None:
        """Time from the restart of node i until it answers, and until it has every block the other nodes have."""
        answering = None
        while self.now() - restarted_at < self.resync_timeout_s:
            head = self.network.head(i)
            if head is not None and answering is None:
                answering = self.now()
            others = [h for j in range(len(self.network.urls)) if j != i and (h := self.network.head(j)) is not None]
            if head is not None and others and head >= max(others):
                self._note(f"node:{i}", "resynced", answering_after_s=round(answering - restarted_at, 3),
                           resynced_after_s=round(self.now() - restarted_at, 3), block=head)
                return
            time.sleep(0.25)
        self._note(f"node:{i}", "resync_timeout")

    def finish(self) -> dict:
        """The stream has ended: stop the schedule, repair whatever is still down (restarted nodes are waited for
        until they have resynced) and return the record of the run."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        for fault in self.faults:
            if fault.target in self.snapshot():
                self._apply(fault, "up", at_end_of_stream=True)
        for t in self._resyncs:
            t.join()
        return {"schedule": [asdict(f) for f in self.faults], "log": list(self.log), "epoch0": self.epoch0}
