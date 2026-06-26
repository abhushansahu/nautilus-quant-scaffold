from __future__ import annotations

from nautilus_zerodte.actors.ingestion import IngestionPlannerActorConfig, plan_subscriptions
from nautilus_zerodte.models.ingestion import IngestionBudget


def test_plan_subscriptions_hot_warm_tiers() -> None:
    budget = IngestionBudget(max_chain_subscriptions=3)
    plan = plan_subscriptions(
        underlying="BTC-PERPETUAL.DERIBIT",
        option_series_id="BTC",
        hedge_perp_instrument="BTC-PERPETUAL.DERIBIT",
        chain_snapshot_interval_ms=30_000,
        budget=budget,
    )
    assert len(plan.specs) == 3
    assert plan.specs[0].tier == "HOT"
    assert plan.specs[0].instrument_id == "BTC-PERPETUAL.DERIBIT"
    assert plan.specs[2].tier == "WARM"
    assert plan.specs[2].snapshot_interval_ms == 30_000


def test_plan_respects_max_chain_subscriptions() -> None:
    budget = IngestionBudget(max_chain_subscriptions=1)
    plan = plan_subscriptions(
        underlying="SPY.NYSE",
        option_series_id="SPY",
        hedge_perp_instrument=None,
        chain_snapshot_interval_ms=60_000,
        budget=budget,
    )
    assert len(plan.specs) == 1


def test_ingestion_planner_actor_config_defaults() -> None:
    config = IngestionPlannerActorConfig()
    assert config.max_chain_subscriptions == 3
