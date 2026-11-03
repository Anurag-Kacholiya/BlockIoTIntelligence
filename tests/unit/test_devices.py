from src.common.config import load_config
from src.data.preparation.devices import capture_to_device, device_map


def test_every_capture_has_a_device():
    captures = load_config("datasets")["realistic"]["captures"]
    mapping = capture_to_device()
    assert set(mapping) == set(captures) and len(mapping) == 24


def test_each_normal_sensor_is_its_own_device():
    captures = load_config("datasets")["realistic"]["captures"]
    mapping = capture_to_device()
    normal = [mapping[c] for c, s in captures.items() if s["kind"] == "normal"]
    assert len(normal) == len(set(normal)) == 10


def test_attacks_belong_to_the_attacked_segment_device():
    captures = load_config("datasets")["realistic"]["captures"]
    mapping = capture_to_device()
    dm = device_map()
    target = dm["attack_segment_device"]
    assert all(mapping[c] == target for c, s in captures.items() if s["kind"] == "attack")
    assert dm["devices"][target]["edge_server_ip"] == "192.168.0.128"      # Table VI: attacked edge server


def test_modbus_and_flame_share_hosts_so_ids_are_by_sensor():
    d = device_map()["devices"]
    assert "192.168.7.62" in d["modbus_tcp"]["node_ip"] and d["g1006_flame"]["node_ip"] == "192.168.7.62"


def test_share_budget_is_equal_exact_and_passes_on_unused_shares():
    from src.data.preparation.realistic import share_budget

    sizes = {"flood": 1_000_000, "sensor": 50_000, "mitm": 184, "scan": 3_000}
    b = share_budget(sizes, 20_000)
    assert sum(b.values()) == 20_000
    assert b["mitm"] == 184 and b["scan"] == 3_000            # small captures give everything they have
    assert abs(b["flood"] - b["sensor"]) <= 1                  # the rest is shared equally
    assert share_budget(sizes, None) == sizes and share_budget(sizes, 10**9) == sizes
    assert share_budget({"a": 5, "b": 5}, 3) in ({"a": 2, "b": 1}, {"a": 1, "b": 2})
