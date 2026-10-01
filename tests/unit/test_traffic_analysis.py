from datetime import UTC, datetime, timedelta

from src.fog.traffic_analysis import TrafficAnalyzer

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_window_counts_and_expiry():
    ta = TrafficAnalyzer([1, 5], flood_events_per_second=100)
    for i in range(10):                      # one event every 0.5 s, from 0.0 s to 4.5 s
        stats = ta.observe("d", T0 + timedelta(seconds=0.5 * i))
    assert stats["events_1s"] == 3           # 3.5, 4.0, 4.5
    assert stats["events_5s"] == 10
    assert stats["last_interarrival_s"] == 0.5


def test_devices_are_independent_and_flood_flag():
    ta = TrafficAnalyzer([1], flood_events_per_second=5)
    for i in range(20):
        burst = ta.observe("noisy", T0 + timedelta(milliseconds=10 * i))
    quiet = ta.observe("quiet", T0)
    assert ta.is_flooding(burst)
    assert not ta.is_flooding(quiet)
