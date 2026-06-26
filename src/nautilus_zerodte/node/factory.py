from __future__ import annotations

from pathlib import Path

from nautilus_trader.backtest.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableFeeModelConfig,
)
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.config import ImportableActorConfig, ImportableStrategyConfig, LoggingConfig
from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import InstrumentClass
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from nautilus_zerodte.config.schema import (
    AppConfig,
    ReferenceStrategyConfig,
    StrategyRuntimeConfig,
    resolved_option_expiry_time,
    resolved_option_multiplier,
    resolved_option_series_id,
    resolved_option_venue,
    resolved_settlement_currency,
)
from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.models.enums import GateStage, VenueAdapter
from nautilus_zerodte.node.adapters.registry import (
    apply_venue_client_wiring,
    build_venue_client_wiring,
    register_venue_factories,
)
from nautilus_zerodte.node.streaming import build_nt_streaming_config

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


def _gate_strategy_config(
    config: AppConfig,
    runtime: StrategyRuntimeConfig | None = None,
) -> dict:
    runtime = runtime or config.strategy
    return {
        "min_edge_after_cost_bps": (
            runtime.min_edge_after_cost_bps
            if runtime.min_edge_after_cost_bps is not None
            else config.gates.min_edge_after_cost_bps
        ),
        "min_liquidity_score": (
            runtime.min_liquidity_score
            if runtime.min_liquidity_score is not None
            else config.gates.min_liquidity_score
        ),
        "blocked_regimes": tuple(
            runtime.blocked_regimes
            if runtime.blocked_regimes is not None
            else config.regime.blocked_regimes
        ),
        "require_chain_snapshot": config.operational.require_chain_snapshot,
        "max_underlying_quote_age_secs": config.operational.max_underlying_quote_age_secs,
        "risk_policy": config.risk.model_dump(mode="json"),
    }


def _reference_strategy_config(
    config: AppConfig,
    reference: ReferenceStrategyConfig,
    runtime: StrategyRuntimeConfig | None = None,
) -> dict:
    runtime = runtime or config.strategy
    return {
        **_gate_strategy_config(config, runtime),
        "dry_run": config.dry_run,
        "venue_adapter": config.venue.adapter.value,
        "fee_schedule": config.fees.model_dump(mode="json"),
        "max_chain_snapshot_age_secs": config.operational.max_chain_snapshot_age_secs,
        "chain_snapshot_interval_ms": config.subscriptions.chain_snapshot_interval_ms,
        "backtest_plumbing": reference.backtest_plumbing,
        "structure_selector": reference.structure_selector,
        "option_series_id": resolved_option_series_id(
            config, underlying=runtime.underlying, reference=reference
        ),
        "option_series_expiry": reference.option_series_expiry,
        "option_series_expiry_time_utc": resolved_option_expiry_time(config, reference),
        "option_venue": resolved_option_venue(config, reference),
        "option_multiplier": resolved_option_multiplier(config, reference),
        "settlement_currency": resolved_settlement_currency(config, reference),
        "strike_width": reference.strike_width,
        "order_qty": reference.order_qty,
        "take_profit_pct": reference.take_profit_pct,
        "stop_loss_pct": reference.stop_loss_pct,
        "hedge_perp_instrument": reference.hedge_perp_instrument,
        "hedge_delta_band": reference.hedge_delta_band,
    }


def _strategy_config(
    config: AppConfig,
    journal_path: Path,
    runtime: StrategyRuntimeConfig | None = None,
) -> ImportableStrategyConfig:
    runtime = runtime or config.strategy
    strategy_class = runtime.strategy_class
    resolved_class = strategy_class if strategy_class in _STRATEGY_PATHS else "gated_skeleton"
    paths = _STRATEGY_PATHS[resolved_class]
    reference = runtime.reference or config.reference
    base_config: dict = {
        "strategy_id": runtime.strategy_id,
        "journal_path": str(journal_path),
        "underlying": runtime.underlying,
    }
    if resolved_class == "gated_skeleton":
        base_config.update(_gate_strategy_config(config, runtime))
    elif resolved_class == "reference":
        base_config["selector_enabled"] = config.selector_enabled()
        base_config.update(_reference_strategy_config(config, reference, runtime))
    return ImportableStrategyConfig(
        strategy_path=paths[0],
        config_path=paths[1],
        config=base_config,
    )


def _strategy_configs(config: AppConfig, journal_path: Path) -> list[ImportableStrategyConfig]:
    runtimes = config.resolved_strategies()
    return [_strategy_config(config, journal_path, runtime) for runtime in runtimes]


def _actor_configs(config: AppConfig) -> list[ImportableActorConfig]:
    primary = config.resolved_strategies()[0]
    actors = [
        ImportableActorConfig(
            actor_path="nautilus_zerodte.actors.session:SessionActor",
            config_path="nautilus_zerodte.actors.session:SessionActorConfig",
            config={
                "blackout_minutes_before_close": config.session.blackout_minutes_before_close,
                "market_close_utc": config.session.market_close_utc,
                "underlying": primary.underlying,
            },
        ),
        ImportableActorConfig(
            actor_path="nautilus_zerodte.actors.regime:RegimeActor",
            config_path="nautilus_zerodte.actors.regime:RegimeActorConfig",
            config={
                "underlying": primary.underlying,
                "trend_move_pct": config.regime.trend_move_pct,
                "chop_range_pct": config.regime.chop_range_pct,
                "pin_strike_proximity_pct": config.regime.pin_strike_proximity_pct,
            },
        ),
    ]
    if config.selector_enabled():
        journal_path = config.resolved_journal_path()
        actors.append(
            ImportableActorConfig(
                actor_path="nautilus_zerodte.actors.selector:SelectorActor",
                config_path="nautilus_zerodte.actors.selector:SelectorActorConfig",
                config={
                    "journal_path": str(journal_path),
                    "diversification": config.diversification.model_dump(mode="json"),
                    "approval": config.approval.model_dump(mode="json"),
                    "batch_interval_ms": config.diversification.batch_interval_ms,
                },
            )
        )
    if config.ingestion.enabled:
        primary = config.resolved_strategies()[0]
        reference = primary.reference or config.reference
        actors.append(
            ImportableActorConfig(
                actor_path="nautilus_zerodte.actors.ingestion:IngestionPlannerActor",
                config_path="nautilus_zerodte.actors.ingestion:IngestionPlannerActorConfig",
                config={
                    "underlying": primary.underlying,
                    "option_series_id": resolved_option_series_id(
                        config,
                        underlying=primary.underlying,
                        reference=reference,
                    ),
                    "hedge_perp_instrument": reference.hedge_perp_instrument,
                    "chain_snapshot_interval_ms": config.subscriptions.chain_snapshot_interval_ms,
                    "max_chain_subscriptions": config.ingestion.budget.max_chain_subscriptions,
                    "max_snapshot_interval_ms": config.ingestion.budget.max_snapshot_interval_ms,
                    "min_snapshot_interval_ms": config.ingestion.budget.min_snapshot_interval_ms,
                },
            )
        )
    return actors


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
    primary = config.resolved_strategies()[0]
    use_option_chain = (
        primary.strategy_class == "reference"
        and not config.reference.backtest_plumbing
        and "option_greeks" in data_types
        and config.venue.adapter in {VenueAdapter.DERIBIT, VenueAdapter.IB}
    )

    if not use_option_chain:
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


def _backtest_fee_model(config: AppConfig) -> ImportableFeeModelConfig | None:
    if config.reference.backtest_plumbing:
        return None
    if config.venue.adapter is VenueAdapter.DERIBIT:
        if config.fees.model != "maker_taker":
            return None
        return ImportableFeeModelConfig(
            fee_model_path="nautilus_trader.backtest.models.fee:MakerTakerFeeModel",
            config_path="nautilus_trader.backtest.config:MakerTakerFeeModelConfig",
            config={},
        )
    if config.venue.adapter is VenueAdapter.IB:
        if config.fees.model != "fixed_per_contract":
            return None
        currency = config.venue.base_currency
        return ImportableFeeModelConfig(
            fee_model_path="nautilus_trader.backtest.models.fee:FixedFeeModel",
            config_path="nautilus_trader.backtest.config:FixedFeeModelConfig",
            config={"commission": f"{config.fees.commission_per_contract} {currency}"},
        )
    return None


def _backtest_venue_config(config: AppConfig) -> BacktestVenueConfig:
    currency = config.venue.base_currency
    fee_model = _backtest_fee_model(config)
    return BacktestVenueConfig(
        name=config.venue.name,
        oms_type="HEDGING",
        account_type=config.venue.account_type,
        base_currency=currency,
        starting_balances=[f"100000 {currency}"],
        fee_model=fee_model,
    )


def build_backtest_node(config: AppConfig, catalog_path: Path | str) -> BacktestNode:
    """Build a BacktestNode wired with actors, strategy, and catalog data."""
    catalog = Path(catalog_path)
    instrument_id = InstrumentId.from_str(config.resolved_strategies()[0].underlying)
    start_time, end_time = _catalog_time_bounds(catalog, instrument_id)
    journal_path = config.resolved_journal_path()

    engine_config = BacktestEngineConfig(
        trader_id=config.trader_id,
        actors=_actor_configs(config),
        strategies=_strategy_configs(config, journal_path),
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
    streaming = (
        build_nt_streaming_config(config.streaming) if config.streaming.enabled else None
    )
    node_config = TradingNodeConfig(
        trader_id=config.trader_id,
        logging=LoggingConfig(log_level="ERROR"),
        actors=_actor_configs(config),
        strategies=_strategy_configs(config, journal_path),
        streaming=streaming,
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
