"""Edge ingestion checks that need no blockchain: schema, duplicates, sequence order (ADR §4.2 edge 1-2, §14.2).

Blockchain-backed checks (hash vs on-chain commitment, registered signer) are added in Phase 4.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import ValidationError

from src.common.schemas import TelemetryEvent


class IngestGate:
    def __init__(self, validate_schema: bool = True):
        self.validate_schema = validate_schema
        self.seen_event_ids: set[str] = set()
        self.last_sequence: dict[str, int] = defaultdict(lambda: -1)

    def check(self, event: dict) -> str | None:
        """Return None if the event passes, otherwise the rejection reason. Does not change state:
        call commit() only once every other check (e.g. the ledger) has also passed, so a forged event
        cannot advance a device's sequence counter and lock out its genuine traffic."""
        if self.validate_schema:
            try:
                TelemetryEvent.model_validate({k: v for k, v in event.items() if k in TelemetryEvent.model_fields})
            except ValidationError:
                return "schema"
        if event["event_id"] in self.seen_event_ids:
            return "duplicate_event"
        if event["sequence_number"] <= self.last_sequence[event["device_id"]]:
            return "sequence_regression"   # replayed or reordered event
        return None

    def commit(self, event: dict) -> None:
        self.seen_event_ids.add(event["event_id"])
        self.last_sequence[event["device_id"]] = event["sequence_number"]
