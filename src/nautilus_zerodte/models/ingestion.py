from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SubscriptionSpec:
    """Planned NT subscription — tier and interval only; no fetch logic."""

    instrument_id: str
    tier: str
    snapshot_interval_ms: int | None = None
    rationale: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "tier": self.tier,
            "snapshot_interval_ms": self.snapshot_interval_ms,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class IngestionBudget:
    max_chain_subscriptions: int = 3
    max_snapshot_interval_ms: int = 300_000
    min_snapshot_interval_ms: int = 30_000


@dataclass(frozen=True, slots=True)
class SubscriptionPlan:
    specs: tuple[SubscriptionSpec, ...] = field(default_factory=tuple)

    def to_payload(self) -> dict[str, Any]:
        return {"specs": [spec.to_payload() for spec in self.specs]}
