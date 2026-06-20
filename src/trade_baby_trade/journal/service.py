from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from trade_baby_trade.models.enums import GateStage
from trade_baby_trade.models.journal import JournalEntry


class Journal:
    """Append-only audit log with in-memory index and JSONL persistence."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[JournalEntry] = []

    @property
    def entries(self) -> list[JournalEntry]:
        return list(self._entries)

    def record(
        self,
        stage: GateStage,
        ref_id: UUID | None = None,
        payload: dict[str, Any] | None = None,
        *,
        strategy_id: str | None = None,
        level: str = "INFO",
    ) -> JournalEntry:
        entry = JournalEntry(
            stage=stage,
            ref_id=ref_id,
            strategy_id=strategy_id,
            level=level,
            payload=payload or {},
        )
        self._entries.append(entry)
        self._append_jsonl(entry)
        return entry

    def _append_jsonl(self, entry: JournalEntry) -> None:
        line = entry.model_dump(mode="json")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, default=str) + "\n")

    @classmethod
    def load(cls, path: Path | str) -> list[JournalEntry]:
        journal_path = Path(path)
        if not journal_path.exists():
            return []
        entries: list[JournalEntry] = []
        with journal_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                entries.append(JournalEntry.model_validate_json(line))
        return entries

    def summary(self) -> dict[str, Any]:
        stage_counts: dict[str, int] = {}
        for entry in self._entries:
            stage_counts[entry.stage.value] = stage_counts.get(entry.stage.value, 0) + 1
        return {
            "total": len(self._entries),
            "stage_counts": stage_counts,
            "last_entries": [e.model_dump(mode="json") for e in self._entries[-10:]],
        }
