"""Final task 3: the gateway's commit scheduling of Merkle batches (src/device/commit_policy.py), on hand-made streams
that need neither a chain nor the dataset."""

from datetime import timedelta

import numpy as np
import pytest

from src.cloud.train_forecaster import rate_probability, samples
from src.device.commit_policy import (
    FEATURES,
    CommitPolicy,
    CommitScheduler,
    TrafficHistory,
    future_rounds,
    make_policy,
    simulate,
)
from src.device.simulator import REPLAY_EPOCH


def ev(device, t, flag=None):
    e = {"device_id": device, "timestamp": REPLAY_EPOCH + timedelta(seconds=t)}
    if flag is not None:
        e["device_inference"] = {"prediction": flag}
    return e


class Stream:
    """Minimal replay: device per message and replay offsets, as RealtimeReplay exposes them."""

    def __init__(self, devices, offsets):
        self.device_of, self.offsets = np.array(devices), np.array(offsets, dtype=float)
        self.device_ids = sorted(set(devices))

    def __len__(self):
        return len(self.device_of)


class ConstantForecaster:
    model_id = "constant"

    def __init__(self, p):
        self.p = p

    def probability(self, history, devices, remaining):
        return np.full(len(devices), self.p)


def col(x, name):
    return x[:, FEATURES.index(name)]


def test_traffic_history_features_by_hand():
    h = TrafficHistory(["a", "b"])
    h.observe(["a", "a", "b"], [0.0, 1.0, 1.5])        # round 0
    h.observe(["b"], [2.0])                            # round 1: a is quiet
    h.observe(["a", "b"], [3.0, 4.0])                  # round 2
    x = h.features(["a", "b"], [1, 2])
    assert list(col(x, "msgs_this_round")) == [1, 1] and list(col(x, "msgs_prev_round")) == [0, 1]
    assert list(col(x, "msgs_2_rounds_ago")) == [2, 1] and list(col(x, "rounds_since_last")) == [0, 0]
    assert list(col(x, "last_gap_rounds")) == [2, 1] and list(col(x, "mean_gap_rounds")) == [2, 1]
    assert list(col(x, "active_share")) == pytest.approx([2 / 3, 1.0])
    assert list(col(x, "msgs_per_round")) == pytest.approx([1.0, 1.0])
    assert col(x, "round_span_s")[0] == 1.0 and col(x, "recent_span_s")[0] == pytest.approx((1.5 + 0 + 1) / 3)
    assert col(x, "active_devices_share")[0] == 1.0
    assert list(col(x, "quiet_s")) == [1.0, 0.0]       # round 2 ends at 4.0
    assert list(col(x, "mean_interarrival_s")) == [1.5, pytest.approx(2.5 / 2)]   # a: 0, 1, 3; b: 1.5, 2, 4
    span = (1.5 + 0 + 1) / 3
    assert list(col(x, "expected_msgs")) == pytest.approx([1 * span / 1.5, 2 * span / 1.25])
    assert list(col(x, "rounds_to_next")) == pytest.approx([(1.5 - 1.0) / span, 1.25 / span])
    assert col(x, "span_trend")[0] == pytest.approx(1.0 / span)


def test_fixed_commits_every_device_every_round_in_arrival_order():
    s = CommitScheduler(CommitPolicy(), ["a", "b"])
    batch = [ev("b", 0.0), ev("a", 0.1), ev("b", 0.2)]
    assert s.step(batch) == batch
    assert s.stats["roots"] == 2 and s.stats["held_message_rounds"] == 0 and not s.pending


def test_rule_holds_small_batches_for_at_most_hold_rounds_and_keeps_device_order():
    s = CommitScheduler(make_policy({"policy": "rule", "hold_rounds": 1, "break_even": 2}), ["a", "b"])
    r0 = [ev("a", 0.0), ev("b", 0.1), ev("b", 0.2), ev("b", 0.3)]
    assert s.step(r0) == [r0[1], r0[2], r0[3]]          # b has 3 > break_even messages: committed; a is held
    r1 = [ev("a", 1.0)]
    assert s.step(r1) == [r0[0], r1[0]]                 # a's batch has waited its one round: committed, in order
    assert s.stats["roots"] == 2 and s.stats["held_message_rounds"] == 1
    assert s.stats["merged_roots"] == 1 and s.stats["wasted_holds"] == 0
    s.step([ev("b", 2.0)])                              # held (1 message) ...
    assert s.step([]) and s.stats["wasted_holds"] == 1  # ... and nothing joined it: a hold that saved nothing


def test_the_last_round_commits_everything():
    s = CommitScheduler(make_policy({"policy": "rule", "hold_rounds": 3, "break_even": 10}), ["a"])
    assert s.step([ev("a", 0.0)]) == []
    assert len(s.step([ev("a", 1.0)], final=True)) == 2 and not s.pending


def test_forecast_holds_a_batch_of_m_messages_only_if_m_is_at_most_p_times_break_even():
    batch = [ev("a", 0.0), ev("a", 0.1), ev("a", 0.2), ev("b", 0.3)]
    for p, held in ((0.9, {"a", "b"}), (0.5, {"b"}), (0.2, set())):   # break_even 4: hold if m <= 4p
        s = CommitScheduler(make_policy({"policy": "forecast", "hold_rounds": 1, "break_even": 4},
                                        forecaster=ConstantForecaster(p)), ["a", "b"])
        out = s.step(batch)
        assert set(s.pending) == held and len(out) == len(batch) - sum(3 if d == "a" else 1 for d in held)


def test_oracle_holds_only_when_the_device_really_sends_again_in_time():
    stream = Stream(["a", "b", "a", "c", "c", "c"], [0, 1, 2, 3, 4, 5])   # rounds of 2: a in 0 and 1, b only in 0
    future = future_rounds(stream.device_of, 2)
    assert future == {"a": {0, 1}, "b": {0}, "c": {1, 2}}
    s = CommitScheduler(make_policy({"policy": "oracle", "hold_rounds": 1, "break_even": 4}, future=future),
                        stream.device_ids)
    out = s.step([ev("a", 0), ev("b", 1)])
    assert [e["device_id"] for e in out] == ["b"] and set(s.pending) == {"a"}


def test_interval_commits_every_kth_round():
    s = CommitScheduler(make_policy({"policy": "interval", "every": 2}), ["a"])
    assert s.step([ev("a", 0.0)]) == [] and len(s.step([ev("a", 1.0)])) == 2
    assert s.step([ev("a", 2.0)]) == []


def test_protect_suspicious_never_holds_a_batch_with_a_flagged_message():
    policy = make_policy({"policy": "rule", "hold_rounds": 2, "break_even": 8, "protect_suspicious": True})
    s = CommitScheduler(policy, ["a", "b"])
    out = s.step([ev("a", 0.0, flag=0), ev("b", 0.1, flag=1)])
    assert [e["device_id"] for e in out] == ["b"] and set(s.pending) == {"a"}
    out = s.step([ev("a", 1.0, flag=1)])                # the held batch now holds a flagged message
    assert len(out) == 2 and not s.pending


def test_make_policy_checks_its_inputs():
    for bad in ({"policy": "nope"}, {"policy": "forecast"}, {"policy": "oracle"}):
        with pytest.raises(ValueError):
            make_policy(bad)
    with pytest.raises(ValueError):
        make_policy({"policy": "rule", "hold_rounds": -1})
    assert make_policy(None).describe()["policy"] == "fixed"


@pytest.mark.parametrize("spec", [{"policy": "rule", "hold_rounds": 2, "break_even": 3},
                                  {"policy": "forecast", "hold_rounds": 3, "break_even": 16},
                                  {"policy": "interval", "every": 3}])
def test_no_message_waits_longer_than_the_budget_and_none_is_lost_or_duplicated(spec):
    rng = np.random.default_rng(0)
    devices = [f"d{i}" for i in rng.integers(0, 40, size=1000)]
    stream = Stream(devices, np.sort(rng.random(1000) * 100))
    policy = make_policy(spec, forecaster=ConstantForecaster(0.8))
    r = simulate(stream, policy, batch_size=64)
    budget = spec.get("hold_rounds", spec.get("every", 1) - 1)
    assert r["messages"] == 1000 and r["held_rounds_p95"] <= budget
    assert max(map(int, r["held_roots_by_rounds"]), default=0) <= budget
    fixed = simulate(stream, make_policy({"policy": "fixed"}), batch_size=64)
    assert fixed["roots"] == len({(i // 64, d) for i, d in enumerate(devices)})   # one root per device per round
    assert r["roots"] < fixed["roots"]
    assert r["merged_roots"] + r["wasted_holds"] == sum(r["held_roots_by_rounds"].values())


def test_training_samples_label_whether_the_device_sends_within_the_horizon():
    # rounds of 2 messages: round 0 = a, b; round 1 = b, b; round 2 = a, a (the last round: no sample)
    stream = Stream(["a", "b", "b", "b", "a", "a"], [0, 1, 2, 3, 4, 5])
    s = samples(stream, round_size=2, max_hold=2)
    assert s["round"].tolist() == [0, 0, 0, 0, 1, 1, 1]
    # round 0: a (r=1: not in round 1; r=2: in round 2), b (in round 1); round 1: a quiet for 1 round (r=1 only:
    # sends in round 2), b (not in round 2, and there is no round 3)
    assert s.remaining_rounds.tolist() == [1, 2, 1, 2, 1, 1, 2]
    assert s.rounds_since_last.tolist() == [0, 0, 0, 0, 1, 0, 0]
    assert s.y.tolist() == [0, 1, 1, 1, 1, 0, 0]


def test_rate_reference_is_a_poisson_probability():
    x = np.zeros((3, len(FEATURES)))
    x[:, FEATURES.index("expected_msgs")] = [0.0, 1.0, np.nan]
    assert list(rate_probability(x)) == pytest.approx([0.0, 1 - np.exp(-1), 0.0])
