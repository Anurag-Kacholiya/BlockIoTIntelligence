"""Device identity for the realistic dataset (final task 1, step 4).

Rule (data/metadata/device_map.yaml): every packet is attributed to the registered IoT device on whose network
segment it was captured. Normal captures belong to their sensor; all attack captures were recorded on the
192.168.0.x segment (edge server 192.168.0.128), so they belong to that segment's device.
Device IDs are metadata, never model features.
"""

from __future__ import annotations

from functools import cache

import yaml

from src.common.config import load_config, resolve


@cache
def device_map() -> dict:
    return yaml.safe_load(resolve(load_config("datasets")["realistic"]["device_map"]).read_text())


def capture_to_device() -> dict[str, str]:
    """capture id -> device id, for all 24 captures."""
    dm = device_map()
    by_capture = {v["capture"]: dev for dev, v in dm["devices"].items()}
    captures = load_config("datasets")["realistic"]["captures"]
    out = {}
    for cap, spec in captures.items():
        if spec["kind"] == "normal":
            if cap not in by_capture:
                raise KeyError(f"normal capture {cap} has no device in device_map.yaml")
            out[cap] = by_capture[cap]
        else:
            out[cap] = dm["attack_segment_device"]
    return out
