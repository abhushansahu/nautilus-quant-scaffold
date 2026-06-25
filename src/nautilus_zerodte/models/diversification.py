from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from nautilus_zerodte.models.trade_intent import TradeIntent


class DiversificationPolicy(BaseModel):
    """Multi-strategy capital allocation rules."""

    model_config = ConfigDict(frozen=True)

    top_n: int = 3
    max_per_instrument: int = 1
    max_per_strategy: float = 0.5
    max_gross_risk_pct: float = 1.0


def select_intents(
    intents: list[TradeIntent],
    policy: DiversificationPolicy,
) -> tuple[list[TradeIntent], list[TradeIntent]]:
    """Apply TopN and diversification caps; return (approved, rejected).

    Sort is deterministic: highest ``edge_after_cost_bps`` first, then ``intent_id``.
    """
    if not intents:
        return [], []

    ranked = sorted(
        intents,
        key=lambda intent: (-intent.edge_after_cost_bps, str(intent.intent_id)),
    )
    max_per_strategy = max(1, int(policy.top_n * policy.max_per_strategy))

    approved: list[TradeIntent] = []
    instrument_counts: dict[str, int] = {}
    strategy_counts: dict[str, int] = {}

    for intent in ranked:
        if len(approved) >= policy.top_n:
            break
        if instrument_counts.get(intent.instrument_id, 0) >= policy.max_per_instrument:
            continue
        if strategy_counts.get(intent.strategy_id, 0) >= max_per_strategy:
            continue
        approved.append(intent)
        instrument_counts[intent.instrument_id] = instrument_counts.get(intent.instrument_id, 0) + 1
        strategy_counts[intent.strategy_id] = strategy_counts.get(intent.strategy_id, 0) + 1

    approved_ids = {intent.intent_id for intent in approved}
    rejected = [intent for intent in intents if intent.intent_id not in approved_ids]
    return approved, rejected
