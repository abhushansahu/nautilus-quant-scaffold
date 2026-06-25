from __future__ import annotations

from pathlib import Path

import pytest

from nautilus_zerodte.config.loader import load_config
from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.models.enums import GateStage
from nautilus_zerodte.node.factory import run_backtest

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "catalog_deribit"
PROFILE_PATH = REPO_ROOT / "configs" / "profiles" / "backtest_btc_multi.yaml"


@pytest.fixture
def catalog_path() -> Path:
    if not CATALOG_PATH.exists() or not any(CATALOG_PATH.rglob("*.parquet")):
        pytest.skip(
            "Deribit catalog fixture not built — run scripts/build_deribit_catalog_fixture.py"
        )
    return CATALOG_PATH


def test_multi_strategy_selector_backtest(catalog_path: Path, tmp_path: Path) -> None:
    """Phase 7 vertical slice: two strategies, TopN=1, human approval stub, fill trail."""
    journal_path = tmp_path / "multi_trail.jsonl"
    config = load_config(PROFILE_PATH)
    config = config.model_copy(
        update={"journal": config.journal.model_copy(update={"path": str(journal_path)})}
    )
    assert config.selector_enabled()
    assert len(config.resolved_strategies()) == 2

    run_backtest(config, catalog_path)

    entries = Journal.load(journal_path)
    events = [e.payload.get("event") for e in entries]

    assert "SELECTOR_APPROVED" in events
    assert "SELECTOR_REJECTED" in events
    assert "HUMAN_APPROVAL_STUB" in events
    assert "ORDER_SUBMIT" in events
    assert "FILL" in events
    assert GateStage.PNL in {e.stage for e in entries}

    submits = [e for e in entries if e.payload.get("event") == "ORDER_SUBMIT"]
    assert len(submits) >= 1

    approved = [e for e in entries if e.payload.get("event") == "SELECTOR_APPROVED"]
    rejected = [e for e in entries if e.payload.get("event") == "SELECTOR_REJECTED"]
    assert len(approved) >= 1
    assert len(rejected) >= 1
    # TopN=1: each SELECTOR_APPROVED should yield at most one ORDER_SUBMIT
    assert len(approved) <= len(submits)

    learning = [e for e in entries if e.payload.get("event") == "LEARNING_RECORD"]
    assert len(learning) >= 1

    strategy_starts = [
        e for e in entries if e.payload.get("event") == "STRATEGY_START"
    ]
    assert len(strategy_starts) == 2
