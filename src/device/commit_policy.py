"""When the device gateway commits each device's Merkle batch (final task 3, RQ-11 AI-driven blockchain).

In Merkle batch mode every micro-batch ("round") of the stream ends with one root per device that sent in it: a
`commitBatch` transaction plus the edge's `recordProcessing` for it, ~149k gas together, whatever the number of
messages under the root. With many devices most roots cover one or two messages (task 2 §10.7). The gateway may
instead keep a device's batch open for up to `hold_rounds` more rounds, so later messages of the device join the
same root; every round a message waits adds one round of latency to it.

Each policy decides, per round and per device with pending messages, whether to hold the batch:
  fixed     never (one root per device per round: the task 2 design)
  interval  every device commits every k-th round (fixed batching with a longer interval)
  rule      hold if the batch has at most `break_even` messages (assumes the device always sends again)
  forecast  the AI: hold if the batch has at most p × `break_even` messages, p = the forecaster's probability that the
            device sends again within the rounds the batch may still wait
  oracle    the rule, but only when the device really sends again in time (perfect foresight: the bound)

`break_even` is the price of latency: delaying that many messages by one round is worth one root's gas. With
`protect_suspicious`, a batch holding a message the device model flags as an attack is never held, so attack
traffic keeps the latency of the fixed design.

The last round of a stream commits everything. Decisions depend only on the stream seen so far (the oracle also on
its future), so the offline `simulate` and a live run make the same decisions on the same stream.
"""

from __future__ import annotations

from collections import deque
from datetime import timedelta

import numpy as np
from threadpoolctl import ThreadpoolController

from src.device.simulator import REPLAY_EPOCH

POLICIES = ("fixed", "interval", "rule", "forecast", "oracle")
EPOCH_S = REPLAY_EPOCH.timestamp()

# Forecaster inputs, in column order. "Round" = one micro-batch of the stream; times are replay seconds.
FEATURES = [
    "remaining_rounds",        # rounds the batch may still wait (the forecast horizon)
    "msgs_this_round",
    "msgs_prev_round",
    "msgs_2_rounds_ago",
    "rounds_since_last",       # 0 if the device sent in this round
    "last_gap_rounds",         # gap between its last two active rounds
    "mean_gap_rounds",         # mean gap between its active rounds
    "active_share",            # share of rounds with messages since it first sent
    "msgs_per_round",          # messages per round since it first sent
    "round_span_s",            # replay time covered by this round (the pace of the whole stream)
    "recent_span_s",           # mean of the last 3 rounds
    "active_devices_share",    # share of the gateway's devices that sent in this round
    "quiet_s",                 # replay time since its last message, at the end of this round
    "mean_interarrival_s",     # mean gap between its last 9 messages
    "expected_msgs",           # remaining_rounds × recent_span_s / mean_interarrival_s
    "rounds_to_next",          # (mean_interarrival_s - quiet_s) / recent_span_s: rounds until its next message is due
    "span_trend",              # round_span_s / recent_span_s: is the stream slowing down (> 1) or speeding up
]


def event_seconds(event: dict) -> float:
    return event["timestamp"].timestamp() - EPOCH_S


def flagged(event: dict) -> bool:
    """The device model classified the message as an attack."""
    return event.get("device_inference", {}).get("prediction") == 1


class TrafficHistory:
    """What the gateway knows about each device's traffic after each round (online: nothing from later rounds)."""

    RECENT = 9

    def __init__(self, device_ids: list[str]):
        self.index = {d: i for i, d in enumerate(device_ids)}
        n = len(device_ids)
        self.round = -1
        self.counts = np.zeros((3, n))                 # this round, the previous one, two rounds ago
        self.first = np.full(n, -1)
        self.last = np.full(n, -1)                     # last round with messages
        self.last_gap = np.full(n, np.nan)
        self.gap_sum = np.zeros(n)
        self.gap_n = np.zeros(n)
        self.active_rounds = np.zeros(n)
        self.total = np.zeros(n)
        self.last_ts = np.full(n, np.nan)
        self.recent = [deque(maxlen=self.RECENT) for _ in range(n)]
        self.spans: deque[float] = deque(maxlen=3)
        self.round_end = np.nan
        self.active_share = 0.0

    def observe(self, device_ids: list[str], times: list[float]) -> None:
        """Every message that arrived in this round, held or not, in arrival order."""
        self.round += 1
        self.counts = np.roll(self.counts, 1, axis=0)
        self.counts[0] = 0
        for d, t in zip(device_ids, times, strict=True):
            i = self.index[d]
            self.counts[0, i] += 1
            self.recent[i].append(t)
            self.last_ts[i] = t
        active = np.nonzero(self.counts[0])[0]
        before = active[self.last[active] >= 0]
        gap = self.round - self.last[before]
        self.last_gap[before] = gap
        self.gap_sum[before] += gap
        self.gap_n[before] += 1
        self.first[active[self.first[active] < 0]] = self.round
        self.last[active] = self.round
        self.active_rounds[active] += 1
        self.total += self.counts[0]
        self.spans.append(max(times) - min(times) if times else 0.0)
        if times:
            self.round_end = max(times)
        self.active_share = len(active) / len(self.index)

    def since_last(self, device_id: str) -> int:
        return self.round - self.last[self.index[device_id]]

    def features(self, device_ids: list[str], remaining: list[int]) -> np.ndarray:
        """One row per (device, remaining rounds), columns as FEATURES. Devices must have sent at least once."""
        i = np.array([self.index[d] for d in device_ids], dtype=int)
        r = np.asarray(remaining, dtype=float)
        seen = self.round - self.first[i] + 1
        recent_span = float(np.mean(self.spans))
        iat = np.array([(q[-1] - q[0]) / (len(q) - 1) if len(q) > 1 else np.nan for q in (self.recent[k] for k in i)])
        iat = np.maximum(iat, 1e-6)                    # repeated timestamps: avoid an infinite expected count
        with np.errstate(invalid="ignore", divide="ignore"):
            mean_gap = np.where(self.gap_n[i] > 0, self.gap_sum[i] / self.gap_n[i], np.nan)
        quiet = self.round_end - self.last_ts[i]
        span = max(recent_span, 1e-6)
        return np.column_stack([
            r, self.counts[0, i], self.counts[1, i], self.counts[2, i], self.round - self.last[i], self.last_gap[i],
            mean_gap, self.active_rounds[i] / seen, self.total[i] / seen, np.full(len(i), self.spans[-1]),
            np.full(len(i), recent_span), np.full(len(i), self.active_share), quiet, iat, r * recent_span / iat,
            (iat - quiet) / span, np.full(len(i), self.spans[-1] / span),
        ])


class CommitPolicy:
    """hold(scheduler) -> devices whose pending batch stays open this round."""

    name = "fixed"
    model = None                                       # the forecaster's registered model, if the policy uses one

    def __init__(self, hold_rounds: int = 1, break_even: float = 16, protect_suspicious: bool = False):
        if hold_rounds < 0 or break_even < 0:
            raise ValueError("hold_rounds and break_even must be >= 0")
        self.hold_rounds, self.break_even, self.protect_suspicious = hold_rounds, break_even, protect_suspicious

    def describe(self) -> dict:
        return {"policy": self.name, "hold_rounds": self.hold_rounds, "break_even": self.break_even,
                "protect_suspicious": self.protect_suspicious}

    def candidates(self, s: CommitScheduler) -> list[str]:
        """Pending batches that may still wait and are small enough to be worth holding at all (p <= 1)."""
        return [d for d, batch in s.pending.items()
                if s.age[d] < self.hold_rounds and len(batch) <= self.break_even
                and not (self.protect_suspicious and any(flagged(e) for _, e in batch))]

    def hold(self, s: CommitScheduler) -> set[str]:
        return set()


class Interval(CommitPolicy):
    """Every device commits every `every` rounds; `hold_rounds` = every - 1, break_even is not used."""

    name = "interval"

    def __init__(self, every: int = 2, protect_suspicious: bool = False):
        if every < 1:
            raise ValueError("every must be >= 1")
        super().__init__(hold_rounds=every - 1, break_even=float("inf"), protect_suspicious=protect_suspicious)
        self.every = every

    def describe(self) -> dict:
        return super().describe() | {"every": self.every, "break_even": None}

    def hold(self, s: CommitScheduler) -> set[str]:
        return set() if (s.round + 1) % self.every == 0 else set(self.candidates(s))


class Rule(CommitPolicy):
    name = "rule"

    def hold(self, s: CommitScheduler) -> set[str]:
        return set(self.candidates(s))


class Forecast(CommitPolicy):
    """The AI policy. `forecaster.probability(history, devices, remaining)` -> P(device sends within remaining)."""

    name = "forecast"

    def __init__(self, forecaster, **kw):
        super().__init__(**kw)
        self.forecaster = forecaster
        self.model = forecaster

    def describe(self) -> dict:
        return super().describe() | {"model_id": getattr(self.forecaster, "model_id", None)}

    def hold(self, s: CommitScheduler) -> set[str]:
        devices = self.candidates(s)
        if not devices:
            return set()
        p = self.forecaster.probability(s.history, devices, [self.hold_rounds - s.age[d] for d in devices])
        return {d for d, pd in zip(devices, p, strict=True) if len(s.pending[d]) <= pd * self.break_even}


class Oracle(CommitPolicy):
    """The rule with perfect foresight: `future[device]` = the rounds in which the device sends."""

    name = "oracle"

    def __init__(self, future: dict[str, set[int]], **kw):
        super().__init__(**kw)
        self.future = future

    def hold(self, s: CommitScheduler) -> set[str]:
        return {d for d in self.candidates(s)
                if any(s.round + k in self.future[d] for k in range(1, self.hold_rounds - s.age[d] + 1))}


class TrafficForecaster:
    """The registered forecaster (models/<view>/device_forecaster/, trained by src/cloud/train_forecaster.py), loaded
    only if its artifact matches its recorded hash; registered and verified on-chain like the layer models."""

    def __init__(self, model_id: str | None = None):
        from src.cloud.model_registry import FORECASTER, layer_dir, load_model
        from src.common.schemas import Layer

        self.model, self.record = load_model(Layer.DEVICE, model_id, kind=FORECASTER)
        if self.record["features"] != FEATURES:
            raise ValueError(f"{self.record['model_id']} was trained on other features")
        self.model_id: str = self.record["model_id"]
        self.path = layer_dir(Layer.DEVICE, FORECASTER) / self.record["artifact"]
        self._threads = ThreadpoolController()

    def probability(self, history: TrafficHistory, devices: list[str], remaining: list[int]) -> np.ndarray:
        # One thread, as the layer models (n_jobs=1): a round asks about a few hundred devices at most, and spreading
        # that over every core costs ~10x more than it saves (25 vs 2 ms for 150 devices), more under the validators'
        # load; on a 1 s block schedule that can push a round past a block boundary.
        with self._threads.limit(limits=1, user_api="openmp"):
            return self.model.predict_proba(history.features(devices, remaining))[:, 1]


def future_rounds(device_of, batch_size: int) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for i, d in enumerate(device_of):
        out.setdefault(str(d), set()).add(i // batch_size)
    return out


def make_policy(spec: dict | None, *, forecaster=None, future: dict[str, set[int]] | None = None) -> CommitPolicy:
    """spec: {"policy": name, "hold_rounds", "break_even", "protect_suspicious", "every" (interval)}."""
    spec = dict(spec or {"policy": "fixed"})
    name = spec.pop("policy")
    if name not in POLICIES:
        raise ValueError(f"unknown commit policy {name!r}; choose from {POLICIES}")
    if name == "interval":
        return Interval(**spec)
    if name == "forecast":
        if forecaster is None:
            raise ValueError("the forecast policy needs a forecaster")
        return Forecast(forecaster, **spec)
    if name == "oracle":
        if future is None:
            raise ValueError("the oracle needs the stream's future rounds")
        return Oracle(future, **spec)
    return Rule(**spec) if name == "rule" else CommitPolicy(**spec)


class CommitScheduler:
    """The gateway's open Merkle batches: sealed messages wait here, per device, until the policy commits them.

    step(events, final) is called once per round with that round's arrivals and returns the messages to commit now,
    in arrival order. A device's messages are always committed together and in order, so per-device sequence
    numbers still increase at the edge. Statistics: roots, held message-rounds, holds that saved a root."""

    def __init__(self, policy: CommitPolicy, device_ids: list[str]):
        self.policy = policy
        self.history = TrafficHistory(device_ids)
        self.pending: dict[str, list[tuple[int, dict]]] = {}   # device -> [(arrival number, event)]
        self.age: dict[str, int] = {}                          # rounds the device's oldest pending message waited
        self.rounds_of: dict[str, set[int]] = {}               # rounds the pending messages arrived in
        self.round = -1
        self._arrivals = 0
        self.stats = {"rounds": 0, "messages": 0, "roots": 0, "held_message_rounds": 0, "holds": 0,
                      "merged_roots": 0, "wasted_holds": 0, "held_roots_by_rounds": {}}

    def step(self, events: list[dict], final: bool = False) -> list[dict]:
        self.round += 1
        for d in self.pending:
            self.age[d] += 1
        self.history.observe([e["device_id"] for e in events], [event_seconds(e) for e in events])
        for e in events:
            d = e["device_id"]
            if d not in self.pending:
                self.pending[d], self.age[d], self.rounds_of[d] = [], 0, set()
            self.pending[d].append((self._arrivals, e))
            self.rounds_of[d].add(self.round)
            self._arrivals += 1
        hold = set() if final else self.policy.hold(self)
        released: list[tuple[int, dict]] = []
        st = self.stats
        for d in list(self.pending):
            if d in hold:
                st["holds"] += 1
                st["held_message_rounds"] += len(self.pending[d])
                continue
            released += self.pending.pop(d)
            st["roots"] += 1
            if self.age[d] > 0:                        # the batch was held at least once
                merged = len(self.rounds_of[d]) > 1
                st["merged_roots" if merged else "wasted_holds"] += 1
                key = str(self.age[d])
                st["held_roots_by_rounds"][key] = st["held_roots_by_rounds"].get(key, 0) + 1
            del self.age[d], self.rounds_of[d]
        st["rounds"] += 1
        st["messages"] += len(events)
        released.sort(key=lambda x: x[0])
        return [e for _, e in released]

    def summary(self) -> dict:
        st = dict(self.stats)
        n = st["messages"] or 1
        st |= {"messages_per_root": st["messages"] / max(1, st["roots"]),
               "held_rounds_per_message": st["held_message_rounds"] / n}
        return self.policy.describe() | st


def timing_events(sim, batch_size: int, flags: np.ndarray | None = None):
    """The stream's rounds as the scheduler sees them, without feature values: device id, the same real timestamp a
    live run builds, the message's position in the stream ("i") and optionally the device model's attack flag. For
    training the forecaster and for offline simulation."""
    for start in range(0, len(sim), batch_size):
        yield [{"i": i, "device_id": str(sim.device_of[i]),
                "timestamp": REPLAY_EPOCH + timedelta(seconds=float(sim.offsets[i])),
                **({"device_inference": {"prediction": int(flags[i])}} if flags is not None else {})}
               for i in range(start, min(start + batch_size, len(sim)))]


def simulate(sim, policy: CommitPolicy, batch_size: int = 256, attack_label: np.ndarray | None = None,
             flags: np.ndarray | None = None) -> dict:
    """Run a policy over a whole stream offline: roots and waiting, exactly as a live run would decide them.
    attack_label (per message, stream order) splits the waiting into attack and normal messages."""
    scheduler = CommitScheduler(policy, sim.device_ids)
    n_rounds = -(-len(sim) // batch_size)
    waited = np.zeros(len(sim))
    for k, events in enumerate(timing_events(sim, batch_size, flags)):
        for e in scheduler.step(events, final=k == n_rounds - 1):
            waited[e["i"]] = k - e["i"] // batch_size
    out = scheduler.summary() | {"held_rounds_p95": float(np.percentile(waited, 95))}
    if attack_label is not None:
        attack = np.asarray(attack_label) == 1
        out |= {"held_rounds_per_attack_message": float(waited[attack].mean()) if attack.any() else 0.0,
                "held_rounds_per_normal_message": float(waited[~attack].mean()) if (~attack).any() else 0.0}
    return out
