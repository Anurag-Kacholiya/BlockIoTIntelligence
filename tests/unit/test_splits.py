import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import train_test_split

from src.data.preparation.splits import leave_one_device_out, session_cuts, split, time_partition, time_split


def _events(seed=0):
    """Two normal sensors (one with two sessions) and one attack capture on the first sensor's segment."""
    rng = np.random.default_rng(seed)
    parts = []
    for capture, device, label, session, n in [
        ("temp", "sensor_a", "Normal", 0, 400), ("temp", "sensor_a", "Normal", 1, 200),
        ("water", "sensor_b", "Normal", 0, 300), ("ddos", "sensor_a", "DDoS_TCP", 0, 500),
    ]:
        start = 10**15 + session * 10**10
        parts.append(pd.DataFrame({
            "capture": capture, "device_id": device, "session": session,
            "ts_us": np.sort(start + rng.integers(0, 10**8, n)), "packet_no": np.arange(n) + session * 1000,
            "Attack_type": label, "Attack_label": int(label != "Normal"), "f": rng.normal(size=n),
        }))
    return pd.concat(parts, ignore_index=True)


def test_time_split_is_disjoint_complete_and_ordered():
    df = _events()
    parts = time_split(df, session_cuts(df))
    assert sum(len(p) for p in parts.values()) == len(df)
    assert set().union(*(set(p.index) for p in parts.values())) == set(df.index)   # with the sum: disjoint
    for key, g in df.groupby(["capture", "session"]):
        p = {name: part[(part.capture == key[0]) & (part.session == key[1])] for name, part in parts.items()}
        assert p["train"].ts_us.max() < p["validation"].ts_us.min()
        assert p["validation"].ts_us.max() < p["test"].ts_us.min()
        assert abs(len(p["train"]) / len(g) - 0.70) < 0.02 and abs(len(p["test"]) / len(g) - 0.15) < 0.02


def test_cuts_from_full_traffic_survive_sampling():
    df = _events()
    cuts = session_cuts(df)
    full = pd.Series(time_partition(df, cuts), index=df.index)
    sample = df.sample(frac=0.3, random_state=1)
    assert (time_partition(sample, cuts) == full.loc[sample.index].to_numpy()).all()


def test_rows_at_a_cut_go_to_the_later_part():
    df = pd.DataFrame({"capture": "c", "session": 0, "ts_us": [1, 2, 3, 4, 5, 6, 7, 8, 8, 8]})
    assert time_partition(df, session_cuts(df)).tolist() == ["train"] * 7 + ["test"] * 3


def test_unknown_session_is_an_error():
    df = _events()
    other = df.assign(session=9)
    with pytest.raises(ValueError):
        time_partition(other, session_cuts(df))


def test_leave_one_device_out_never_trains_on_the_held_out_sensor():
    df = _events()
    cuts = session_cuts(df)
    parts = leave_one_device_out(df, cuts, "sensor_a")
    held = (df.Attack_label == 0) & (df.device_id == "sensor_a")
    for name in ("train", "validation"):
        p = parts[name]
        assert not ((p.Attack_label == 0) & (p.device_id == "sensor_a")).any()
    assert set(df[held].index) <= set(parts["test"].index)
    # attacks recorded on the same segment are still learned (split by time)
    assert (parts["train"].Attack_label == 1).any() and (parts["test"].Attack_label == 1).any()
    assert sum(len(p) for p in parts.values()) == len(df)
    assert set().union(*(set(p.index) for p in parts.values())) == set(df.index)
    with pytest.raises(ValueError):
        leave_one_device_out(df, cuts, "no_such_sensor")


def test_random_split_reproduces_the_mid_term_protocol():
    df = _events()
    parts = split(df, seed=42, stratify="Attack_type")
    old_train, old_rest = train_test_split(df, test_size=0.30, stratify=df["Attack_type"], random_state=42)
    _, old_test = train_test_split(old_rest, test_size=0.5, stratify=old_rest["Attack_type"], random_state=42)
    assert parts["train"].index.equals(old_train.index) and parts["test"].index.equals(old_test.index)


def test_random_split_stratifies_by_class_and_device():
    df = _events()
    parts = split(df, seed=42, stratify=["Attack_type", "device_id"])
    share = parts["test"].groupby(["Attack_type", "device_id"]).size() / df.groupby(["Attack_type", "device_id"]).size()
    assert ((share - 0.15).abs() < 0.01).all()
