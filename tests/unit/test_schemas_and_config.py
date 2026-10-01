from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.common.config import config_hash, load_config
from src.common.schemas import Layer, TelemetryEvent


def test_all_configs_load():
    for name in ("base", "datasets", "models", "blockchain", "experiments"):
        assert load_config(name), name


def test_split_fractions_sum_to_one():
    split = load_config("datasets")["edge_iiotset"]["split"]
    assert split["train"] + split["validation"] + split["test"] == pytest.approx(1.0)


def test_config_hash_is_stable():
    assert config_hash("base", "datasets") == config_hash("datasets", "base")


def test_telemetry_event_rejects_unknown_fields_and_negative_sequence():
    base = dict(
        event_id="e", device_id="d", trace_id="t", timestamp=datetime.now(UTC), sequence_number=0,
        values={}, source_file="f.csv", source_row_id=0, attack_label=0, attack_type="Normal",
    )
    assert TelemetryEvent(**base).layer is Layer.DEVICE
    with pytest.raises(ValidationError):
        TelemetryEvent(**base | {"sequence_number": -1})
    with pytest.raises(ValidationError):
        TelemetryEvent(**base | {"unexpected": 1})
