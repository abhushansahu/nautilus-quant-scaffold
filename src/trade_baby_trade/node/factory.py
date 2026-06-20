from __future__ import annotations

import os
from pathlib import Path

from nautilus_trader.backtest.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
)
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.config import ImportableStrategyConfig, LoggingConfig
from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from trade_baby_trade.config.schema import AppConfig
from trade_baby_trade.journal.service import Journal
from trade_baby_trade.models.enums import GateStage


def _skeleton_strategy_config(config: AppConfig, journal_path: Path) -> ImportableStrategyConfig:
    return ImportableStrategyConfig(
        strategy_path="trade_baby_trade.strategies.skeleton:SkeletonZeroDteStrategy",
        config_path="trade_baby_trade.strategies.skeleton:SkeletonZeroDteStrategyConfig",
        config={
            "strategy_id": config.strategy.strategy_id,
            "journal_path": str(journal_path),
            "underlying": config.strategy.underlying,
        },
    )


def _catalog_time_bounds(catalog_path: Path, instrument_id: InstrumentId) -> tuple[int, int]:
    catalog = ParquetDataCatalog(str(catalog_path))
    ticks = catalog.quote_ticks(instrument_ids=[instrument_id])
    if not ticks:
        msg = f"No quote ticks for {instrument_id} in catalog at {catalog_path}"
        raise ValueError(msg)
    return ticks[0].ts_event, ticks[-1].ts_event


def build_backtest_node(config: AppConfig, catalog_path: Path | str) -> BacktestNode:
    """Build a BacktestNode wired with the skeleton strategy and catalog data."""
    catalog = Path(catalog_path)
    instrument_id = InstrumentId.from_str(config.strategy.underlying)
    start_time, end_time = _catalog_time_bounds(catalog, instrument_id)
    journal_path = config.resolved_journal_path()

    engine_config = BacktestEngineConfig(
        trader_id=config.trader_id,
        strategies=[_skeleton_strategy_config(config, journal_path)],
        logging=LoggingConfig(bypass_logging=True),
    )
    venue_config = BacktestVenueConfig(
        name=config.venue.name,
        oms_type="HEDGING",
        account_type="MARGIN",
        base_currency="USD",
        starting_balances=["100000 USD"],
    )
    data_config = BacktestDataConfig(
        catalog_path=str(catalog),
        catalog_fs_protocol="file",
        data_cls=QuoteTick,
        instrument_id=instrument_id,
        start_time=start_time,
        end_time=end_time,
    )
    run_config = BacktestRunConfig(
        engine=engine_config,
        venues=[venue_config],
        data=[data_config],
    )
    return BacktestNode(configs=[run_config])


def build_trading_node(config: AppConfig) -> TradingNode:
    """Build a TradingNode with skeleton strategy and optional IB adapter."""
    journal_path = config.resolved_journal_path()
    node_config = TradingNodeConfig(
        trader_id=config.trader_id,
        logging=LoggingConfig(log_level="ERROR"),
        strategies=[_skeleton_strategy_config(config, journal_path)],
    )

    if _ib_adapter_available() and not config.dry_run:
        _attach_ib_clients(node_config, config)

    return TradingNode(config=node_config)


def _ib_adapter_available() -> bool:
    try:
        import ibapi  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("IB_HOST"))


def _attach_ib_clients(node_config: TradingNodeConfig, config: AppConfig) -> None:
    from nautilus_trader.adapters.interactive_brokers.common import IB
    from nautilus_trader.adapters.interactive_brokers.config import (
        InteractiveBrokersDataClientConfig,
        InteractiveBrokersExecClientConfig,
        InteractiveBrokersInstrumentProviderConfig,
    )
    from nautilus_trader.adapters.interactive_brokers.factories import (
        InteractiveBrokersLiveDataClientFactory,
        InteractiveBrokersLiveExecClientFactory,
    )

    ib_config = {
        "host": config.ib.host,
        "port": config.ib.port,
        "client_id": config.ib.client_id,
    }
    instrument_provider = InteractiveBrokersInstrumentProviderConfig(
        load_all=False,
        load_ids=frozenset(),
    )
    node_config.data_clients = {
        IB: InteractiveBrokersDataClientConfig(
            ib_gateway=ib_config,
            instrument_provider=instrument_provider,
        ),
    }
    node_config.exec_clients = {
        IB: InteractiveBrokersExecClientConfig(
            ib_gateway=ib_config,
            instrument_provider=instrument_provider,
        ),
    }
    node_config.data_client_factories = [InteractiveBrokersLiveDataClientFactory]
    node_config.exec_client_factories = [InteractiveBrokersLiveExecClientFactory]


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
