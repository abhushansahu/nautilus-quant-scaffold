from __future__ import annotations

import json
from pathlib import Path

from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.models.enums import GateStage


def test_journal_record_and_persist(tmp_path: Path) -> None:
    journal_path = tmp_path / "test.jsonl"
    journal = Journal(journal_path)
    journal.record(
        GateStage.LIFECYCLE,
        payload={"event": "NODE_START"},
    )
    journal.record(
        GateStage.LIFECYCLE,
        payload={"event": "STRATEGY_START"},
        strategy_id="skeleton-001",
    )
    assert len(journal.entries) == 2
    assert journal_path.exists()

    loaded = Journal.load(journal_path)
    assert len(loaded) == 2
    assert loaded[1].strategy_id == "skeleton-001"


def test_journal_summary(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "test.jsonl")
    journal.record(GateStage.LIFECYCLE, payload={"event": "NODE_START"})
    journal.record(GateStage.SESSION, payload={"passed": False})
    summary = journal.summary()
    assert summary["total"] == 2
    assert summary["stage_counts"]["LIFECYCLE"] == 1
    assert summary["stage_counts"]["SESSION"] == 1


def test_journal_jsonl_is_valid_json(tmp_path: Path) -> None:
    journal_path = tmp_path / "test.jsonl"
    journal = Journal(journal_path)
    journal.record(GateStage.LIFECYCLE, payload={"event": "NODE_START"})
    with journal_path.open() as handle:
        line = handle.readline()
    parsed = json.loads(line)
    assert parsed["stage"] == "LIFECYCLE"
    assert parsed["payload"]["event"] == "NODE_START"
