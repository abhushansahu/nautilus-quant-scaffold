"""Backtest runner: experiment config -> NautilusTrader BacktestEngine -> persisted results."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import TraderId, Venue
from nautilus_trader.model.objects import Money

from analysis.metrics import summarize_performance
from analysis.runs import load_equity, load_trade_pnls
from apps.backtester.results import RunArtifacts, append_run_index, make_run_id, write_run_results
from core.config import AppConfig
from core.experiment import ExperimentConfig
from data_pipeline.loader import BarDataLoader, DataWindow, default_loader
from models.inference import SignalModel
from nt_ext.factories import build_strategy
from nt_ext.risk.engine import build_risk_engine_config

# The Rust logging subsystem can only be initialized once per process; keep the
# first engine's LogGuard alive so sequential runs (e.g. parameter sweeps) work.
_LOG_GUARD = None


def _config_hash(exp: ExperimentConfig) -> str:
    payload = json.dumps(exp.model_dump(mode="json"), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _data_range_from_bars(bars: list) -> dict[str, str | None]:
    if not bars:
        return {"data_start": None, "data_end": None}
    from nautilus_trader.core.datetime import unix_nanos_to_dt

    return {
        "data_start": unix_nanos_to_dt(bars[0].ts_event).isoformat(),
        "data_end": unix_nanos_to_dt(bars[-1].ts_event).isoformat(),
    }


def run_experiment(
    exp: ExperimentConfig,
    app_cfg: AppConfig,
    signal_model: SignalModel | None = None,
    results_dir: Path | None = None,
    data_window: DataWindow | None = None,
    profile_name: str | None = None,
    suite_name: str | None = None,
    cache_key: str | None = None,
    index_dir: Path | None = None,
    loader: BarDataLoader | None = None,
) -> RunArtifacts:
    """Run a single experiment end-to-end and persist its results. Returns the artifacts."""
    if signal_model is None and exp.strategy.model_artifact is not None:
        from models.jax_signal import JaxSignalModel  # deferred: requires the models dep group

        signal_model = JaxSignalModel.from_artifact(exp.strategy.model_artifact)

    bar_loader = loader or default_loader()
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

        instrument = bar_loader.resolve_instrument(exp, app_cfg)
        bars = bar_loader.load_bars(
            exp,
            app_cfg,
            instrument,
            data_window=data_window,
            cache_key=cache_key,
        )
        data_range = _data_range_from_bars(bars)

        engine.add_instrument(instrument)
        engine.add_data(bars)
        engine.add_strategy(build_strategy(exp.strategy, risk=risk, signal_model=signal_model))

        engine.run()

        fills = engine.trader.generate_order_fills_report()
        positions = engine.trader.generate_positions_report()
        account = engine.trader.generate_account_report(venue)

        final_balance = (
            float(account.iloc[-1]["total"]) if not account.empty else float(starting_balance)
        )
        metrics: dict[str, float | int | str] = {
            "n_fills": int(len(fills)),
            "n_positions": int(len(positions)),
            "starting_balance": float(starting_balance),
            "final_balance": final_balance,
            "pnl": final_balance - float(starting_balance),
            "currency": str(starting_balance.currency),
        }

        out_dir = results_dir or app_cfg.results_dir
        run_id = make_run_id(exp.name)
        artifacts = write_run_results(
            results_dir=out_dir,
            run_id=run_id,
            fills=fills,
            positions=positions,
            account=account,
            config_snapshot=exp.model_dump(mode="json"),
            metrics=metrics,
            data_range=data_range,
        )

        perf = summarize_performance(load_equity(artifacts.run_dir), load_trade_pnls(artifacts.run_dir))
        artifacts.summary["metrics"].update(perf)
        artifacts.summary["data_range"] = data_range
        artifacts.summary["config_hash"] = _config_hash(exp)
        (artifacts.run_dir / "summary.json").write_text(
            json.dumps(artifacts.summary, indent=2, default=str)
        )

        if profile_name is not None:
            append_run_index(
                results_dir=index_dir or out_dir,
                artifacts=artifacts,
                profile_name=profile_name,
                suite_name=suite_name or exp.name,
                data_range=data_range,
            )

        return artifacts
    finally:
        engine.dispose()
