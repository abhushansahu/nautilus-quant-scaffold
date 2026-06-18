"""Integration: watcher detects new catalog bars and updates the run index."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from nautilus_trader.model.data import BarType
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from apps.backtester.watcher import BacktestWatcher
from core.config import load_config
from core.run_profile import RunProfile, RunSuite
from data_pipeline.catalog import MarketDataCatalog
from data_pipeline.ingestion.synthetic import generate_bars
from data_pipeline.watermarks import WatermarkStore

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
START = datetime(2024, 1, 1, tzinfo=UTC)
BAR_TYPE = BarType.from_str("EUR/USD.SIM-1-MINUTE-MID-EXTERNAL")
BAR_TYPE_STR = str(BAR_TYPE)
INSTRUMENT = TestInstrumentProvider.default_fx_ccy("EUR/USD")

pytestmark = pytest.mark.integration


@pytest.fixture
def watcher_setup(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog"
    results_dir = tmp_path / "results"
    state_dir = tmp_path / "state"
    watermark_path = state_dir / "watermarks.json"
    active_path = state_dir / "active_strategy.json"

    catalog = MarketDataCatalog(catalog_path)
    bars = generate_bars(BAR_TYPE, INSTRUMENT, start=START, num_bars=100, seed=42)
    catalog.write_instrument(INSTRUMENT)
    catalog.write_bars(bars[:50])

    suite = RunSuite(
        name="watcher_test",
        poll_interval_secs=1,
        bar_types=[BAR_TYPE_STR],
        parallelism=1,
        profiles=[
            RunProfile(
                name="ema_fast",
                experiment=Path("strategies/ema_cross_demo.yaml"),
                environment="backtest",
                results_dir=results_dir / "ema_fast",
            ),
            RunProfile(
                name="ema_slow",
                experiment=Path("strategies/ema_cross_slow.yaml"),
                environment="backtest",
                results_dir=results_dir / "ema_slow",
            ),
        ],
    )

    app_cfg = load_config("backtest", config_dir=CONFIG_DIR).model_copy(
        update={
            "catalog_path": catalog_path,
            "results_dir": results_dir,
            "logging": load_config("backtest", config_dir=CONFIG_DIR).logging.model_copy(
                update={"level": "ERROR"}
            ),
        }
    )
    monkeypatch.setattr("apps.backtester.watcher.load_config", lambda *a, **k: app_cfg)
    monkeypatch.setattr("core.config.load_config", lambda *a, **k: app_cfg)

    watcher = BacktestWatcher(
        suite,
        config_dir=CONFIG_DIR,
        watermark_store=WatermarkStore(watermark_path),
        state_path=active_path,
    )
    return watcher, catalog, bars, results_dir, active_path, watermark_path


def test_watcher_triggers_on_new_data(watcher_setup):
    watcher, catalog, bars, results_dir, active_path, watermark_path = watcher_setup

    assert watcher.run_once()
    assert (results_dir / "index.jsonl").exists()
    assert active_path.exists()
    assert watermark_path.exists()

    index_lines = [
        json.loads(line) for line in (results_dir / "index.jsonl").read_text().splitlines()
    ]
    assert len(index_lines) == 2

    assert not watcher.run_once()

    catalog.write_bars(bars[50:60])
    assert watcher.run_once()
    index_lines_after = [
        json.loads(line) for line in (results_dir / "index.jsonl").read_text().splitlines()
    ]
    assert len(index_lines_after) == 4
