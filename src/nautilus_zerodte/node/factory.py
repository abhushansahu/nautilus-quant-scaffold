from __future__ import annotations

from pathlib import Path

from nautilus_trader.backtest.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
)
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.config import ImportableActorConfig, ImportableStrategyConfig, LoggingConfig
from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import InstrumentClass
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from nautilus_zerodte.config.schema import AppConfig
from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.models.enums import GateStage, VenueAdapter
from nautilus_zerodte.node.adapters.registry import (
    apply_venue_client_wiring,
    build_venue_client_wiring,
    register_venue_factories,
)

_STRATEGY_PATHS: dict[str, tuple[str, str]] = {
    "skeleton": (
        "nautilus_zerodte.strategies.skeleton:SkeletonZeroDteStrategy",
        "nautilus_zerodte.strategies.skeleton:SkeletonZeroDteStrategyConfig",
    ),
    "gated_skeleton": (
        "nautilus_zerodte.strategies.gated_skeleton:GatedSkeletonStrategy",
        "nautilus_zerodte.strategies.gated_skeleton:GatedSkeletonStrategyConfig",
    ),
    "reference": (
        "nautilus_zerodte.strategies.reference:ReferenceZeroDteStrategy",
        "nautilus_zerodte.strategies.reference:ReferenceZeroDteStrategyConfig",
    ),
}


def _gate_strategy_config(config: AppConfig) -> dict:
    return {
        "min_edge_after_cost_bps": config.gates.min_edge_after_cost_bps,
        "min_liquidity_score": config.gates.min_liquidity_score,
        "blocked_regimes": tuple(config.regime.blocked_regimes),
        "require_chain_snapshot": config.operational.require_chain_snapshot,
        "max_underlying_quote_age_secs": config.operational.max_underlying_quote_age_secs,
        "risk_policy": config.risk.model_dump(mode="json"),
    }


def _reference_strategy_config(config: AppConfig) -> dict:
    return {
        **_gate_strategy_config(config),
        "dry_run": config.dry_run,
        "venue_adapter": config.venue.adapter.value,
        "max_chain_snapshot_age_secs": config.operational.max_chain_snapshot_age_secs,
        "chain_snapshot_interval_ms": config.subscriptions.chain_snapshot_interval_ms,
        "backtest_plumbing": config.reference.backtest_plumbing,
        "structure_selector": config.reference.structure_selector,
        "option_series_id": config.reference.option_series_id,
        "option_series_expiry": config.reference.option_series_expiry,
        "option_series_expiry_time_utc": config.reference.option_series_expiry_time_utc,
        "settlement_currency": config.reference.settlement_currency,
        "strike_width": config.reference.strike_width,
        "order_qty": config.reference.order_qty,
        "take_profit_pct": config.reference.take_profit_pct,
        "stop_loss_pct": config.reference.stop_loss_pct,
        "hedge_perp_instrument": config.reference.hedge_perp_instrument,
        "hedge_delta_band": config.reference.hedge_delta_band,
    }


def _strategy_config(config: AppConfig, journal_path: Path) -> ImportableStrategyConfig:
    strategy_class = config.strategy.strategy_class
    resolved_class = strategy_class if strategy_class in _STRATEGY_PATHS else "gated_skeleton"
    paths = _STRATEGY_PATHS[resolved_class]
    base_config: dict = {
        "strategy_id": config.strategy.strategy_id,
        "journal_path": str(journal_path),
        "underlying": config.strategy.underlying,
    }
    if resolved_class == "gated_skeleton":
        base_config.update(_gate_strategy_config(config))
    elif resolved_class == "reference":
        base_config.update(_reference_strategy_config(config))
    return ImportableStrategyConfig(
        strategy_path=paths[0],
        config_path=paths[1],
        config=base_config,
    )


def _actor_configs(config: AppConfig) -> list[ImportableActorConfig]:
    return [
        ImportableActorConfig(
            actor_path="nautilus_zerodte.actors.session:SessionActor",
            config_path="nautilus_zerodte.actors.session:SessionActorConfig",
            config={
                "blackout_minutes_before_close": config.session.blackout_minutes_before_close,
                "market_close_utc": config.session.market_close_utc,
                "underlying": config.strategy.underlying,
            },
        ),
        ImportableActorConfig(
            actor_path="nautilus_zerodte.actors.regime:RegimeActor",
            config_path="nautilus_zerodte.actors.regime:RegimeActorConfig",
            config={
                "underlying": config.strategy.underlying,
                "trend_move_pct": config.regime.trend_move_pct,
                "chop_range_pct": config.regime.chop_range_pct,
                "pin_strike_proximity_pct": config.regime.pin_strike_proximity_pct,
            },
        ),
    ]


def _catalog_time_bounds(catalog_path: Path, instrument_id: InstrumentId) -> tuple[int, int]:
    catalog = ParquetDataCatalog(str(catalog_path))
    ticks = catalog.quote_ticks(instrument_ids=[instrument_id])
    if not ticks:
        msg = f"No quote ticks for {instrument_id} in catalog at {catalog_path}"
        raise ValueError(msg)
    return ticks[0].ts_event, ticks[-1].ts_event


def _backtest_data_configs(
    config: AppConfig,
    catalog_path: Path,
    instrument_id: InstrumentId,
    start_time: int,
    end_time: int,
) -> list[BacktestDataConfig]:
    """Build BacktestDataConfig entries for catalog contents."""
    catalog = ParquetDataCatalog(str(catalog_path))
    data_types = set(catalog.list_data_types())
    use_deribit_chain = (
        config.venue.adapter is VenueAdapter.DERIBIT
        and not config.reference.backtest_plumbing
        and "option_greeks" in data_types
    )

    if not use_deribit_chain:
        return [
            BacktestDataConfig(
                catalog_path=str(catalog_path),
                catalog_fs_protocol="file",
                data_cls=QuoteTick,
                instrument_id=instrument_id,
                start_time=start_time,
                end_time=end_time,
            )
        ]

    quote_ids = [str(inst.id) for inst in catalog.instruments()]
    configs = [
        BacktestDataConfig(
            catalog_path=str(catalog_path),
            catalog_fs_protocol="file",
            data_cls=QuoteTick,
            instrument_ids=quote_ids,
            start_time=start_time,
            end_time=end_time,
        )
    ]
    option_ids = [
        str(inst.id)
        for inst in catalog.instruments()
        if inst.instrument_class == InstrumentClass.OPTION
    ]
    if option_ids:
        configs.append(
            BacktestDataConfig(
                catalog_path=str(catalog_path),
                catalog_fs_protocol="file",
                data_cls="nautilus_trader.model.data:OptionGreeks",
                instrument_ids=option_ids,
                start_time=start_time,
                end_time=end_time,
            )
        )
    return configs


def _backtest_venue_config(config: AppConfig) -> BacktestVenueConfig:
    currency = config.venue.base_currency
    return BacktestVenueConfig(
        name=config.venue.name,
        oms_type="HEDGING",
        account_type=config.venue.account_type,
        base_currency=currency,
        starting_balances=[f"100000 {currency}"],
    )


def build_backtest_node(config: AppConfig, catalog_path: Path | str) -> BacktestNode:
    """Build a BacktestNode wired with actors, strategy, and catalog data."""
    catalog = Path(catalog_path)
    instrument_id = InstrumentId.from_str(config.strategy.underlying)
    start_time, end_time = _catalog_time_bounds(catalog, instrument_id)
    journal_path = config.resolved_journal_path()

    engine_config = BacktestEngineConfig(
        trader_id=config.trader_id,
        actors=_actor_configs(config),
        strategies=[_strategy_config(config, journal_path)],
        logging=LoggingConfig(bypass_logging=True),
    )
    data_config = _backtest_data_configs(config, catalog, instrument_id, start_time, end_time)
    run_config = BacktestRunConfig(
        engine=engine_config,
        venues=[_backtest_venue_config(config)],
        data=data_config,
    )
    return BacktestNode(configs=[run_config])


def build_trading_node(config: AppConfig) -> TradingNode:
    """Build a TradingNode with actors, strategy, and venue adapter wiring."""
    journal_path = config.resolved_journal_path()
    node_config = TradingNodeConfig(
        trader_id=config.trader_id,
        logging=LoggingConfig(log_level="ERROR"),
        actors=_actor_configs(config),
        strategies=[_strategy_config(config, journal_path)],
    )

    wiring = build_venue_client_wiring(config, dry_run=config.dry_run)
    node_config = apply_venue_client_wiring(node_config, wiring)

    node = TradingNode(config=node_config)
    register_venue_factories(node, wiring)

    return node


def run_backtest(config: AppConfig, catalog_path: Path | str) -> Journal:
    """Run backtest with node lifecycle journal entries."""
    journal_path = config.resolved_journal_path()
    journal = Journal(journal_path)
    journal.record(
        GateStage.LIFECYCLE,
        payload={
            "event": "NODE_START",
            "node": "BacktestNode",
            "trader_id": config.trader_id,
            "risk_policy_version": config.risk.version,
            "venue_adapter": config.venue.adapter.value,
        },
    )
    node = build_backtest_node(config, catalog_path)
    try:
        node.run()
    finally:
        journal.record(
            GateStage.LIFECYCLE,
            payload={"event": "NODE_STOP", "node": "BacktestNode"},
        )
    return journal
