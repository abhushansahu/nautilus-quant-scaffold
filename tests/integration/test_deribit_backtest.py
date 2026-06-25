from __future__ import annotations

from pathlib import Path

import pytest

from nautilus_zerodte.config.loader import load_config
from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.models.enums import GateStage
from nautilus_zerodte.node.factory import run_backtest

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "catalog_deribit"
PROFILE_PATH = REPO_ROOT / "configs" / "profiles" / "backtest_btc.yaml"


@pytest.fixture
def catalog_path() -> Path:
    if not CATALOG_PATH.exists() or not any(CATALOG_PATH.rglob("*.parquet")):
        pytest.skip(
            "Deribit catalog fixture not built — run scripts/build_deribit_catalog_fixture.py"
        )
    return CATALOG_PATH


def test_deribit_backtest_full_journal_trail(catalog_path: Path, tmp_path: Path) -> None:
    """Phase 5 vertical slice: gates → spread order → fill → PnL on Deribit catalog."""
    journal_path = tmp_path / "deribit_trail.jsonl"
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

    greek_pass = [e for e in entries if e.payload.get("event") == "GREEK_PASSED"]
    assert len(greek_pass) >= 1

    fsm_to_in_position = [
        e
        for e in entries
        if e.payload.get("event") == "FSM_TRANSITION" and e.payload.get("to") == "InPosition"
    ]
    assert len(fsm_to_in_position) >= 1

    spread_submits = [
        e
        for e in entries
        if e.payload.get("event") == "ORDER_SUBMIT"
        and "BTC-CS" in str(e.payload.get("instrument_id", ""))
    ]
    assert len(spread_submits) >= 1
