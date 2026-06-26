from __future__ import annotations

from nautilus_trader.common.actor import Actor
from nautilus_trader.config import ActorConfig

from nautilus_zerodte.actors.data_types import INGESTION_PLAN_TOPIC, IngestionPlanSnapshot
from nautilus_zerodte.models.ingestion import IngestionBudget, SubscriptionPlan, SubscriptionSpec


class IngestionPlannerActorConfig(ActorConfig, frozen=True):
    underlying: str = "SPY.NYSE"
    option_series_id: str | None = None
    hedge_perp_instrument: str | None = None
    chain_snapshot_interval_ms: int = 60_000
    max_chain_subscriptions: int = 3
    max_snapshot_interval_ms: int = 300_000
    min_snapshot_interval_ms: int = 30_000


def plan_subscriptions(
    *,
    underlying: str,
    option_series_id: str | None,
    hedge_perp_instrument: str | None,
    chain_snapshot_interval_ms: int,
    budget: IngestionBudget,
) -> SubscriptionPlan:
    """Pure subscription planner — HOT/WARM tiers aligned with ingestion-tiers.md."""
    interval = min(
        max(chain_snapshot_interval_ms, budget.min_snapshot_interval_ms),
        budget.max_snapshot_interval_ms,
    )
    specs: list[SubscriptionSpec] = [
        SubscriptionSpec(
            instrument_id=underlying,
            tier="HOT",
            rationale="underlying quote ticks for delta band / hedge context",
        ),
    ]
    if hedge_perp_instrument:
        specs.append(
            SubscriptionSpec(
                instrument_id=hedge_perp_instrument,
                tier="HOT",
                rationale="perp hedge instrument quote ticks",
            )
        )
    if option_series_id:
        specs.append(
            SubscriptionSpec(
                instrument_id=option_series_id,
                tier="WARM",
                snapshot_interval_ms=interval,
                rationale="option chain snapshots for structure selection",
            )
        )
    return SubscriptionPlan(specs=tuple(specs[: budget.max_chain_subscriptions]))


class IngestionPlannerActor(Actor):
    """Emits a cost-aware subscription plan on start — Strategies call NT subscribe methods."""

    def __init__(self, config: IngestionPlannerActorConfig) -> None:
        super().__init__(config)
        self._budget = IngestionBudget(
            max_chain_subscriptions=config.max_chain_subscriptions,
            max_snapshot_interval_ms=config.max_snapshot_interval_ms,
            min_snapshot_interval_ms=config.min_snapshot_interval_ms,
        )

    def on_start(self) -> None:
        plan = plan_subscriptions(
            underlying=self.config.underlying,
            option_series_id=self.config.option_series_id,
            hedge_perp_instrument=self.config.hedge_perp_instrument,
            chain_snapshot_interval_ms=self.config.chain_snapshot_interval_ms,
            budget=self._budget,
        )
        self.msgbus.publish(
            topic=INGESTION_PLAN_TOPIC,
            msg=IngestionPlanSnapshot(plan=plan.to_payload()),
        )
