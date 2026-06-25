from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RiskPolicy(BaseModel):
    """Greek and desk limits — value object only; no greek math."""

    model_config = ConfigDict(frozen=True)

    max_net_delta: float = 100.0
    max_net_gamma: float = 50.0
    max_net_vega: float = 10_000.0
    max_daily_loss: Decimal | None = None
    max_concentration_per_strike: float = 0.2
    spot_shock: float = 0.01
    vol_shock: float = 0.10
    version: str = "default"

    def check(
        self,
        current_greeks: dict[str, float],
        projected_greeks: dict[str, float],
        *,
        intent_id: UUID | None = None,
    ) -> RiskAssessment:
        """Pure limit check on greek snapshots (Phase 2+)."""
        breached: list[str] = []

        projected_delta = projected_greeks.get("delta", 0.0)
        projected_gamma = projected_greeks.get("gamma", 0.0)
        projected_vega = projected_greeks.get("vega", 0.0)

        if abs(projected_delta) > self.max_net_delta:
            breached.append("max_net_delta")
        if abs(projected_gamma) > self.max_net_gamma:
            breached.append("max_net_gamma")
        if abs(projected_vega) > self.max_net_vega:
            breached.append("max_net_vega")

        return RiskAssessment(
            intent_id=intent_id,
            passed=len(breached) == 0,
            breached_rules=breached,
            projected_greeks=dict(projected_greeks),
            current_greeks=dict(current_greeks),
        )


class RiskAssessment(BaseModel):
    """Output of RiskPolicy.check()."""

    model_config = ConfigDict(frozen=True)

    intent_id: UUID | None = None
    passed: bool
    breached_rules: list[str] = Field(default_factory=list)
    projected_greeks: dict[str, float] = Field(default_factory=dict)
    current_greeks: dict[str, float] = Field(default_factory=dict)
