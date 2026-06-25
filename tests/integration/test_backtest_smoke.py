from __future__ import annotations

from pathlib import Path

import pytest
from nautilus_trader.adapters.deribit import DERIBIT

from nautilus_zerodte.config.loader import load_config
from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.node.factory import build_backtest_node, build_trading_node, run_backtest

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "catalog"
PROFILE_PATH = REPO_ROOT / "configs" / "profiles" / "paper_spy.yaml"
PAPER_BTC_PATH = REPO_ROOT / "configs" / "profiles" / "paper_btc.yaml"


@pytest.fixture
def catalog_path() -> Path:
    if not CATALOG_PATH.exists():
        pytest.skip("Catalog fixture not built — run scripts/build_catalog_fixture.py")
    return CATALOG_PATH


def test_build_backtest_node(catalog_path: Path, tmp_path: Path) -> None:
    config = load_config(PROFILE_PATH)
    config = config.model_copy(
        update={"journal": config.journal.model_copy(update={"path": str(tmp_path / "bt.jsonl")})}
    )
    node = build_backtest_node(config, catalog_path)
    assert node is not None


def test_backtest_lifecycle_journal(catalog_path: Path, tmp_path: Path) -> None:
    journal_path = tmp_path / "lifecycle.jsonl"
    config = load_config(PROFILE_PATH)
    config = config.model_copy(
        update={"journal": config.journal.model_copy(update={"path": str(journal_path)})}
    )
    run_backtest(config, catalog_path)

    entries = Journal.load(journal_path)
    events = [e.payload.get("event") for e in entries]
    assert "NODE_START" in events
    assert "NODE_STOP" in events
    assert "STRATEGY_START" in events
    assert "STRATEGY_STOP" in events


def test_build_trading_node_dry_run(tmp_path: Path) -> None:
    import asyncio

    config = load_config(PROFILE_PATH)
    config = config.model_copy(update={"dry_run": True})
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        node = build_trading_node(config)
        assert node is not None
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def test_build_trading_node_paper_btc_dry_run() -> None:
    import asyncio

    config = load_config(PAPER_BTC_PATH)
    assert config.dry_run is True
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        node = build_trading_node(config)
        assert node is not None
        assert DERIBIT in node._config.data_clients  # noqa: SLF001
        assert DERIBIT in node._config.exec_clients  # noqa: SLF001
        assert DERIBIT in node._builder._data_factories  # noqa: SLF001
        assert DERIBIT in node._builder._exec_factories  # noqa: SLF001
    finally:
        loop.close()
        asyncio.set_event_loop(None)
