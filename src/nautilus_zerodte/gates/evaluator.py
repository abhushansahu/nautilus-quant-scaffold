from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nautilus_zerodte.gates.context import GateContext
from nautilus_zerodte.models.enums import GateStage
from nautilus_zerodte.models.risk import RiskAssessment, RiskPolicy
from nautilus_zerodte.models.trade_intent import TradeIntent


class GateResult(BaseModel):
    """Outcome of a pre-greek gate pipeline stage or full pipeline."""

    model_config = ConfigDict(frozen=True)

    passed: bool
    failed_stage: GateStage | None = None
    breached_rules: list[str] = Field(default_factory=list)


def evaluate_edge(intent: TradeIntent, context: GateContext) -> GateResult:
    if intent.edge_after_cost_bps < context.min_edge_after_cost_bps:
        return GateResult(
            passed=False,
            failed_stage=GateStage.EDGE,
            breached_rules=["min_edge_after_cost_bps"],
        )
    return GateResult(passed=True)


def evaluate_liquidity(intent: TradeIntent, context: GateContext) -> GateResult:
    if intent.liquidity_score < context.min_liquidity_score:
        return GateResult(
            passed=False,
            failed_stage=GateStage.LIQUIDITY,
            breached_rules=["min_liquidity_score"],
        )
    return GateResult(passed=True)


def evaluate_regime(intent: TradeIntent, context: GateContext) -> GateResult:
    tag = context.regime_tag
    if tag in context.blocked_regimes:
        return GateResult(
            passed=False,
            failed_stage=GateStage.REGIME,
            breached_rules=[f"blocked_regime:{tag.value}"],
        )
    if intent.regime_tag in context.blocked_regimes:
        return GateResult(
            passed=False,
            failed_stage=GateStage.REGIME,
            breached_rules=[f"intent_regime:{intent.regime_tag.value}"],
        )
    return GateResult(passed=True)


def evaluate_session(_intent: TradeIntent, context: GateContext) -> GateResult:
    if not context.session_allows_entry:
        return GateResult(
            passed=False,
            failed_stage=GateStage.SESSION,
            breached_rules=["session_blackout"],
        )
    return GateResult(passed=True)


def evaluate_operational(_intent: TradeIntent, context: GateContext) -> GateResult:
    breached: list[str] = []
    if not context.trading_state_active:
        breached.append("trading_state_inactive")
    if not context.underlying_quote_fresh:
        breached.append("underlying_quote_stale")
    if context.require_chain_snapshot and not context.chain_snapshot_fresh:
        breached.append("chain_snapshot_stale")
    if context.daily_loss_breached:
        breached.append("daily_loss_budget")
    if not context.feed_healthy:
        breached.append("feed_unhealthy")
    if breached:
        return GateResult(
            passed=False,
            failed_stage=GateStage.OPERATIONAL,
            breached_rules=breached,
        )
    return GateResult(passed=True)


_PRE_GREEK_STAGES: tuple[tuple[GateStage, object], ...] = (
    (GateStage.EDGE, evaluate_edge),
    (GateStage.LIQUIDITY, evaluate_liquidity),
    (GateStage.REGIME, evaluate_regime),
    (GateStage.SESSION, evaluate_session),
    (GateStage.OPERATIONAL, evaluate_operational),
)


def evaluate_pre_greek(intent: TradeIntent, context: GateContext) -> GateResult:
    """Pure pre-greek gate pipeline: edge → liquidity → regime → session → operational."""
    for _stage, evaluator in _PRE_GREEK_STAGES:
        result = evaluator(intent, context)  # type: ignore[operator]
        if not result.passed:
            return result
    return GateResult(passed=True)


def check_risk_policy(
    policy: RiskPolicy,
    current_greeks: dict[str, float],
    projected_greeks: dict[str, float],
    *,
    intent_id: UUID | None = None,
) -> RiskAssessment:
    """Pure greek limit check — call site wrapper per gate-boundary ADR."""
    return policy.check(
        current_greeks,
        projected_greeks,
        intent_id=intent_id,
    )
