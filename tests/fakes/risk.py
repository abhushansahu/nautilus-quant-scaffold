from __future__ import annotations

from nt_ext.risk.rules import OrderContext, RiskDecision


class FakeOrderRiskRule:
    name = "fake_rule"

    def __init__(self, approved: bool = True, reason: str | None = None) -> None:
        self.approved = approved
        self.reason = reason
        self.checks: list[OrderContext] = []

    def check(self, ctx: OrderContext) -> RiskDecision:
        self.checks.append(ctx)
        if self.approved:
            return RiskDecision.ok()
        return RiskDecision.reject(self.reason or "rejected")
