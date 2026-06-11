"""Composable, pure-Python pre-trade risk rules.

These complement (not replace) NautilusTrader's RiskEngine: the engine enforces
hard platform limits, while these rules express strategy-level policy and are
trivially unit-testable. Strategies evaluate them before submitting orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OrderContext:
    """The facts a rule needs about a prospective order."""

    instrument_id: str
    notional: float
    open_positions: int


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str | None = None

    @staticmethod
    def ok() -> RiskDecision:
        return RiskDecision(approved=True)

    @staticmethod
    def reject(reason: str) -> RiskDecision:
        return RiskDecision(approved=False, reason=reason)


class OrderRiskRule(Protocol):
    name: str

    def check(self, ctx: OrderContext) -> RiskDecision: ...


class MaxNotionalPerOrderRule:
    name = "max_notional_per_order"

    def __init__(self, max_notional: float) -> None:
        if max_notional <= 0:
            raise ValueError("max_notional must be positive")
        self.max_notional = max_notional

    def check(self, ctx: OrderContext) -> RiskDecision:
        if ctx.notional > self.max_notional:
            return RiskDecision.reject(
                f"order notional {ctx.notional:.2f} exceeds limit {self.max_notional:.2f}"
            )
        return RiskDecision.ok()


class MaxOpenPositionsRule:
    name = "max_open_positions"

    def __init__(self, max_positions: int) -> None:
        if max_positions <= 0:
            raise ValueError("max_positions must be positive")
        self.max_positions = max_positions

    def check(self, ctx: OrderContext) -> RiskDecision:
        if ctx.open_positions >= self.max_positions:
            return RiskDecision.reject(
                f"open positions {ctx.open_positions} at limit {self.max_positions}"
            )
        return RiskDecision.ok()


class DrawdownTracker:
    """Tracks peak equity and flags when drawdown from peak breaches the limit.

    Pure state machine so it can be tested without an engine; the strategy base
    feeds it equity marks and halts trading once breached.
    """

    def __init__(self, max_drawdown_pct: float) -> None:
        if not 0 < max_drawdown_pct <= 1:
            raise ValueError("max_drawdown_pct must be in (0, 1]")
        self.max_drawdown_pct = max_drawdown_pct
        self._peak: float | None = None
        self.breached = False

    @property
    def peak(self) -> float | None:
        return self._peak

    def update(self, equity: float) -> bool:
        """Record an equity mark; returns True if the drawdown limit is now breached."""
        if self._peak is None or equity > self._peak:
            self._peak = equity
        if self._peak > 0:
            drawdown = (self._peak - equity) / self._peak
            if drawdown >= self.max_drawdown_pct:
                self.breached = True
        return self.breached
