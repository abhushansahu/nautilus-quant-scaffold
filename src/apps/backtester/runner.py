"""Backtest runner: experiment config -> NautilusTrader BacktestEngine -> persisted results."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import InstrumentId, TraderId, Venue
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Money
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from apps.backtester.results import RunArtifacts, make_run_id, write_run_results
from core.config import AppConfig
from core.experiment import ExperimentConfig
from data_pipeline.catalog import MarketDataCatalog
from data_pipeline.ingestion.synthetic import generate_bars
from models.inference import SignalModel
from nt_ext.factories import build_strategy
from nt_ext.risk.engine import build_risk_engine_config

# The Rust logging subsystem can only be initialized once per process; keep the
# first engine's LogGuard alive so sequential runs (e.g. parameter sweeps) work.
_LOG_GUARD = None


def _resolve_instrument(exp: ExperimentConfig, app_cfg: AppConfig) -> Instrument:
    instrument_id = InstrumentId.from_str(exp.strategy.instrument_id)
    if exp.data.source == "catalog":
        catalog = MarketDataCatalog(app_cfg.catalog_path)
        for instrument in catalog.instruments():
            if instrument.id == instrument_id:
                return instrument
        raise ValueError(f"Instrument {instrument_id} not found in catalog {catalog.path}")
    # Synthetic runs use a standard FX pair definition for the requested symbol/venue.
    return TestInstrumentProvider.default_fx_ccy(
        str(instrument_id.symbol),
        venue=instrument_id.venue,
    )


def _load_bars(exp: ExperimentConfig, app_cfg: AppConfig, instrument: Instrument) -> list:
    bar_type = BarType.from_str(exp.strategy.bar_type)
    if exp.data.source == "catalog":
        catalog = MarketDataCatalog(app_cfg.catalog_path)
        bars = catalog.read_bars(bar_type)
        if not bars:
            raise ValueError(f"No bars for {bar_type} in catalog {catalog.path}")
        return bars
    return generate_bars(
        bar_type=bar_type,
        instrument=instrument,
        start=exp.data.start,
        num_bars=exp.data.num_bars,
        seed=exp.data.seed,
        bar_interval_secs=exp.data.bar_interval_secs,
    )


def run_experiment(
    exp: ExperimentConfig,
    app_cfg: AppConfig,
    signal_model: SignalModel | None = None,
    results_dir: Path | None = None,
) -> RunArtifacts:
    """Run a single experiment end-to-end and persist its results. Returns the artifacts."""
    if signal_model is None and exp.strategy.model_artifact is not None:
        from models.jax_signal import JaxSignalModel  # deferred: requires the models dep group

        signal_model = JaxSignalModel.from_artifact(exp.strategy.model_artifact)

    risk = exp.risk or app_cfg.risk
    venue = Venue(exp.venue.name)
    starting_balance = Money.from_str(exp.venue.starting_balance)

    engine = BacktestEngine(
        config=BacktestEngineConfig(
            trader_id=TraderId("BACKTESTER-001"),
            logging=LoggingConfig(log_level=app_cfg.logging.level),
            risk_engine=build_risk_engine_config(risk, [exp.strategy.instrument_id]),
        )
    )
    global _LOG_GUARD
    if _LOG_GUARD is None:
        _LOG_GUARD = engine.kernel.get_log_guard()
    try:
        engine.add_venue(
            venue=venue,
            oms_type=OmsType.NETTING,
            account_type=AccountType[exp.venue.account_type],
            base_currency=starting_balance.currency,
            starting_balances=[starting_balance],
            default_leverage=Decimal(10),
        )

        instrument = _resolve_instrument(exp, app_cfg)
        engine.add_instrument(instrument)
        engine.add_data(_load_bars(exp, app_cfg, instrument))
        engine.add_strategy(build_strategy(exp.strategy, risk=risk, signal_model=signal_model))

        engine.run()

        fills = engine.trader.generate_order_fills_report()
        positions = engine.trader.generate_positions_report()
        account = engine.trader.generate_account_report(venue)

        final_balance = (
            float(account.iloc[-1]["total"]) if not account.empty else float(starting_balance)
        )
        metrics = {
            "n_fills": int(len(fills)),
            "n_positions": int(len(positions)),
            "starting_balance": float(starting_balance),
            "final_balance": final_balance,
            "pnl": final_balance - float(starting_balance),
            "currency": str(starting_balance.currency),
        }

        return write_run_results(
            results_dir=results_dir or app_cfg.results_dir,
            run_id=make_run_id(exp.name),
            fills=fills,
            positions=positions,
            account=account,
            config_snapshot=exp.model_dump(mode="json"),
            metrics=metrics,
        )
    finally:
        engine.dispose()
