from __future__ import annotations

from pathlib import Path

import pytest

from trade_baby_trade.config.loader import load_config
from trade_baby_trade.journal.service import Journal
from trade_baby_trade.models.enums import GateStage
from trade_baby_trade.node.factory import run_backtest

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "catalog"
PROFILE_PATH = REPO_ROOT / "configs" / "profiles" / "paper_spy.yaml"


@pytest.fixture
def catalog_path() -> Path:
    if not CATALOG_PATH.exists():
        pytest.skip("Catalog fixture not built — run scripts/build_catalog_fixture.py")
    return CATALOG_PATH


def test_backtest_session_gate_rejection(catalog_path: Path, tmp_path: Path) -> None:
    """Phase 2 vertical slice: SESSION gate rejection during T-30m blackout."""
    journal_path = tmp_path / "session_gate.jsonl"
    config = load_config(PROFILE_PATH)
    config = config.model_copy(
        update={
            "journal": config.journal.model_copy(update={"path": str(journal_path)}),
            "session": config.session.model_copy(update={"market_close_utc": "14:45"}),
            "operational": config.operational.model_copy(update={"require_chain_snapshot": False}),
            "gates": config.gates.model_copy(
                update={"min_edge_after_cost_bps": 0.0, "min_liquidity_score": 0.0}
            ),
            "regime": config.regime.model_copy(update={"blocked_regimes": []}),
        }
    )
    run_backtest(config, catalog_path)

    entries = Journal.load(journal_path)
    session_rejects = [
        e
        for e in entries
        if e.stage == GateStage.SESSION and e.payload.get("event") == "GATE_REJECT"
    ]
    assert len(session_rejects) >= 1
    assert "session_blackout" in session_rejects[0].payload["breached_rules"]
    assert session_rejects[0].ref_id is not None
