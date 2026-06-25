from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.learning.module import LearningModule
from nautilus_zerodte.models.enums import GateStage
from nautilus_zerodte.models.trade_intent import TradeIntent


def test_learning_module_records_attribution(tmp_path: Path) -> None:
    journal_path = tmp_path / "learn.jsonl"
    journal = Journal(journal_path)
    module = LearningModule(journal, strategy_id="ref-001")

    intent_id = uuid4()
    intent = TradeIntent(
        intent_id=intent_id,
        strategy_id="ref-001",
        instrument_id="BTC-CS.DERIBIT",
        edge_after_cost_bps=42.0,
    )
    module.register_entry(intent, quote_mid=0.02)

    event = MagicMock()
    event.last_px = 0.0201
    event.last_qty = 0.1
    event.client_order_id = "O-123"
    event.instrument_id = "BTC-CS.DERIBIT"
    event.commission = Decimal("0.000006")

    record = module.on_order_filled(
        event,
        intent=intent,
        intent_id=intent_id,
        realized_pnl=Decimal("0.001"),
    )

    assert record is not None
    assert record.commission == Decimal("0.000006")
    assert record.edge_predicted_bps == 42.0
    assert record.slippage_bps == pytest.approx(50.0, abs=1.0)

    entries = Journal.load(journal_path)
    learning = [e for e in entries if e.stage == GateStage.LEARNING]
    assert len(learning) == 1
    assert learning[0].payload["event"] == "LEARNING_RECORD"
    assert learning[0].payload["commission"] == "0.000006"
