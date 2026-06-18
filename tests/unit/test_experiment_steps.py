from pathlib import Path

from apps.backtester.experiment_steps import (
    build_backtest_engine,
    config_hash,
    data_range_from_bars,
    load_experiment_bars,
)
from core.config import load_config
from core.experiment import load_experiment
from tests.fakes import FakeBarLoader

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class TestExperimentStepHelpers:
    def test_config_hash_stable(self):
        exp = load_experiment(CONFIG_DIR / "strategies" / "ema_cross_demo.yaml")
        assert config_hash(exp) == config_hash(exp)
        assert len(config_hash(exp)) == 16

    def test_data_range_from_empty_bars(self):
        assert data_range_from_bars([]) == {"data_start": None, "data_end": None}


class TestBuildBacktestEngine:
    def test_builds_engine_for_demo_experiment(self):
        app_cfg = load_config("backtest", config_dir=CONFIG_DIR)
        exp = load_experiment(CONFIG_DIR / "strategies" / "ema_cross_demo.yaml")
        engine = build_backtest_engine(app_cfg, exp, app_cfg.risk)
        try:
            assert engine is not None
        finally:
            engine.dispose()


class TestLoadExperimentBars:
    def test_uses_loader_resolve_and_load(self):
        app_cfg = load_config("backtest", config_dir=CONFIG_DIR)
        exp = load_experiment(CONFIG_DIR / "strategies" / "ema_cross_demo.yaml")
        loader = FakeBarLoader(bars=[])
        instrument, bars, data_range = load_experiment_bars(exp, app_cfg, loader)
        assert len(loader.resolve_calls) == 1
        assert len(loader.load_calls) == 1
        assert instrument is not None
        assert bars == []
        assert data_range == {"data_start": None, "data_end": None}
