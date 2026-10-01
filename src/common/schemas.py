"""Canonical domain objects shared by all four intelligence layers (ADR §4.2, §5.1, §8)."""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Layer(IntEnum):
    """Numeric values match the uint8 `layer` argument of IoTRegistry.sol."""

    DEVICE = 0
    EDGE = 1
    FOG = 2
    CLOUD = 3


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TelemetryEvent(_Record):
    """One Edge-IIoTset row as emitted by a logical device (dataset plan step 5)."""

    event_id: str
    device_id: str
    trace_id: str
    layer: Layer = Layer.DEVICE
    timestamp: datetime              # replay time assigned by the simulator (derived, not a dataset column)
    sequence_number: int = Field(ge=0)
    values: dict[str, Any]           # network/protocol features from the source row
    source_dataset: str = "Edge-IIoTset"
    source_file: str
    source_row_id: int
    payload_hash: str | None = None
    previous_event_hash: str | None = None
    signature: str | None = None
    # Ground truth travels with the event for evaluation only; layers must never read it for inference.
    attack_label: int
    attack_type: str


class DataCommitment(_Record):
    event_id: str
    device_id: str
    payload_hash: str
    layer: Layer
    timestamp: datetime


class FeatureRecord(_Record):
    trace_id: str
    event_id: str
    edge_id: str
    features: dict[str, float]
    parent_event_hash: str
    processed_hash: str


class InferenceResult(_Record):
    trace_id: str
    event_id: str
    layer: Layer
    model_id: str
    prediction: str | int
    score: float | None = None
    latency_ms: float


class AttackAlert(_Record):
    alert_id: str
    fog_id: str
    trace_id: str
    event_ids: list[str]
    attack_type: str
    confidence: float
    timestamp: datetime
    alert_hash: str | None = None


class ModelMetadata(_Record):
    """A model counts as valid only when all four provenance hashes/params are recorded (ADR Phase 6)."""

    model_id: str
    layer: Layer
    family: str
    model_hash: str
    training_data_hash: str
    feature_schema_hash: str
    hyperparameters: dict[str, Any]
    framework_version: str
    metrics: dict[str, float]
    trained_at: datetime


class BlockchainReceipt(_Record):
    tx_hash: str
    block_number: int
    gas_used: int
    submitted_at: datetime
    confirmed_at: datetime


class ExperimentMetric(_Record):
    run_id: str
    experiment: str
    layer: Layer | None
    name: str
    value: float
    unit: str
    blockchain: bool
    seed: int
