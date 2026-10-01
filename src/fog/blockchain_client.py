"""Fog blockchain actions: tamper-evident audit trail of attack alerts (ADR §6.5, Phase 5)."""

from __future__ import annotations

from src.common.blockchain import Chain, h32, id32
from src.common.crypto import hash_object
from src.common.schemas import AttackAlert

MAX_ALERTS_PER_TX = 150   # keeps each recordAlerts call well under the block gas limit


class FogChainClient:
    def __init__(self, chain: Chain, sender: str, fog_id: str):
        self.chain, self.sender, self.fog_id = chain, sender, fog_id

    def audit_alerts(self, alerts: list[AttackAlert]) -> None:
        if not alerts:
            return
        calls = []
        for i in range(0, len(alerts), MAX_ALERTS_PER_TX):
            chunk = alerts[i:i + MAX_ALERTS_PER_TX]
            calls.append([
                [id32(a.alert_id) for a in chunk],
                [h32(hash_object(a.model_dump(mode="json", exclude={"alert_hash"}))) for a in chunk],
                id32(self.fog_id),
                int(chunk[0].timestamp.timestamp() * 1000),
            ])
        self.chain.send_many("fog_alert_audit", "recordAlerts", calls, self.sender, gas=10_000_000)
