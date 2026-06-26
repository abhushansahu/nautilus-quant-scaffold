from __future__ import annotations

from pathlib import Path

import pytest

from nautilus_zerodte.config.loader import load_config
from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.models.enums import GateStage
from nautilus_zerodte.node.factory import run_backtest

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "catalog"
PROFILE_PATH = REPO_ROOT / "configs" / "profiles" / "backtest_spy.yaml"


@pytest.fixture
def catalog_path() -> Path:
    if not CATALOG_PATH.exists() or not any(CATALOG_PATH.rglob("*.parquet")):
        pytest.skip("Catalog fixture not built — run scripts/build_catalog_fixture.py")
    return CATALOG_PATH


def test_ib_backtest_full_journal_trail(catalog_path: Path, tmp_path: Path) -> None:
    """Phase 8 vertical slice: gates → BAG spread order → fill → PnL on SPY catalog."""
    journal_path = tmp_path / "ib_spy_trail.jsonl"
    config = load_config(PROFILE_PATH)
    config = config.model_copy(
        update={"journal": config.journal.model_copy(update={"path": str(journal_path)})}
    )
    run_backtest(config, catalog_path)

    entries = Journal.load(journal_path)
    events = [e.payload.get("event") for e in entries]
    stages = {e.stage for e in entries}

    assert "ORDER_SUBMIT" in events
    assert "FILL" in events
    assert GateStage.PNL in stages
    assert GateStage.GREEK in stages

    spread_submits = [
        e
        for e in entries
        if e.payload.get("event") == "ORDER_SUBMIT"
        and "SPY-CS" in str(e.payload.get("instrument_id", ""))
    ]
    assert len(spread_submits) >= 1

    learning = [e for e in entries if e.payload.get("event") == "LEARNING_RECORD"]
    assert len(learning) >= 1

    fills = [e for e in entries if e.payload.get("event") == "FILL"]
    assert len(fills) >= 1
    assert any("commission" in f.payload for f in fills)
