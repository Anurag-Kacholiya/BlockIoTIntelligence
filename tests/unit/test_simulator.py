import numpy as np
import pandas as pd
import pytest

from src.device.simulator import REPLAY_EPOCH, DeviceSimulator, RealtimeReplay


def _rows():
    """Two sensors; sensor_a has two sessions, a day apart. Real gaps in µs."""
    return pd.DataFrame({
        "capture": ["temp", "temp", "temp", "temp", "water", "water"],
        "session": [0, 0, 1, 1, 0, 0],
        "device_id": ["sensor_a"] * 4 + ["sensor_b"] * 2,
        "ts_us": [10**15, 10**15 + 2_000_000, 10**15 + 86_400 * 10**6, 10**15 + 86_400 * 10**6 + 500_000,
                  5 * 10**15 + 1_000_000, 5 * 10**15 + 4_000_000],
        "packet_no": [1, 2, 3, 4, 1, 2],
        "source_row_id": [1, 2, 3, 4, 100_000_001, 100_000_002],
        "f": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        "Attack_label": 0, "Attack_type": "Normal",
    })


def _events(sim, size=2):
    return [e for batch in sim.batches(size) for e in batch]


def test_realtime_replay_keeps_real_gaps_and_devices_but_not_dates():
    events = _events(RealtimeReplay(_rows()))
    offsets = [(e["timestamp"] - REPLAY_EPOCH).total_seconds() for e in events]
    assert offsets == sorted(offsets)
    # every session starts at replay time 0: the absolute capture dates are gone
    assert offsets == [0.0, 0.0, 0.0, 0.5, 2.0, 3.0]
    assert [e["source_row_id"] for e in events] == [1, 3, 100_000_001, 4, 2, 100_000_002]
    assert {e["device_id"] for e in events} == {"sensor_a", "sensor_b"}


def test_realtime_replay_speed_and_limit():
    events = _events(RealtimeReplay(_rows(), speed=10, limit=4))
    assert [(e["timestamp"] - REPLAY_EPOCH).total_seconds() for e in events] == [0.0, 0.0, 0.0, 0.05]
    with pytest.raises(ValueError):
        RealtimeReplay(_rows(), speed=0)


def test_sequence_numbers_count_per_device_in_send_order():
    events = _events(RealtimeReplay(_rows()))
    for device in ("sensor_a", "sensor_b"):
        assert [e["sequence_number"] for e in events if e["device_id"] == device] == list(
            range(sum(e["device_id"] == device for e in events)))


def test_replicas_split_each_device_round_robin_and_keep_timing():
    plain, split = _events(RealtimeReplay(_rows())), _events(RealtimeReplay(_rows(), replicas=2))
    assert [e["source_row_id"] for e in split] == [e["source_row_id"] for e in plain]
    assert [e["timestamp"] for e in split] == [e["timestamp"] for e in plain]
    # sensor_a sends rows 1, 3, 4, 2 (send order) -> replicas 0, 1, 0, 1; sensor_b 100_000_001/2 -> 0, 1
    assert [e["device_id"] for e in split] == ["sensor_a#000", "sensor_a#001", "sensor_b#000", "sensor_a#000",
                                               "sensor_a#001", "sensor_b#001"]
    assert RealtimeReplay(_rows(), replicas=2).device_ids == ["sensor_a#000", "sensor_a#001", "sensor_b#000",
                                                             "sensor_b#001"]
    with pytest.raises(ValueError):
        RealtimeReplay(_rows(), replicas=0)


def test_metadata_never_reaches_the_payload():
    for sim in (RealtimeReplay(_rows()), DeviceSimulator(_rows(), n_devices=3, seed=1)):
        assert all(set(e["values"]) == {"f"} for e in _events(sim))


def test_device_simulator_is_unchanged_by_the_refactor():
    rows, seed, n = _rows(), 7, 3
    rng = np.random.default_rng(seed)
    shuffled = rows.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    device = rng.integers(0, n, size=len(rows))
    offsets = np.cumsum(rng.exponential(1.0 / 1000.0, size=len(rows)))
    events = _events(DeviceSimulator(rows, n, seed))
    assert [e["source_row_id"] for e in events] == shuffled.source_row_id.tolist()
    assert [e["device_id"] for e in events] == [f"device-{d:04d}" for d in device]
    replay_s = [(e["timestamp"] - REPLAY_EPOCH).total_seconds() for e in events]
    assert replay_s == pytest.approx(offsets.tolist(), abs=1e-6)   # timedelta has a µs clock
    assert DeviceSimulator(rows, n, seed).device_ids == ["device-0000", "device-0001", "device-0002"]
