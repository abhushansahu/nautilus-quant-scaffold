from __future__ import annotations

from pathlib import Path

from nautilus_zerodte.journal.service import Journal
from nautilus_zerodte.models.enums import ActorKind, GateStage
from nautilus_zerodte.models.trade_intent import TradeIntent


class HumanApprovalHandler:
    """Stub human approval — journals and auto-approves for Phase 7 plumbing."""

    def __init__(self, journal: Journal) -> None:
        self._journal = journal

    def handle(self, intent: TradeIntent, *, actor_kind: ActorKind) -> bool:
        self._journal.record(
            GateStage.LIFECYCLE,
            ref_id=intent.intent_id,
            payload={
                "event": "HUMAN_APPROVAL_STUB",
                "intent_id": str(intent.intent_id),
                "strategy_id": intent.strategy_id,
                "instrument_id": intent.instrument_id,
                "actor_kind": actor_kind.value,
                "approved": True,
            },
            strategy_id=intent.strategy_id,
        )
        return True


class AutomationHandler:
    """Automation approval path — journals before publish to execution."""

    def __init__(self, journal: Journal) -> None:
        self._journal = journal

    def handle(self, intent: TradeIntent, *, actor_kind: ActorKind) -> bool:
        self._journal.record(
            GateStage.LIFECYCLE,
            ref_id=intent.intent_id,
            payload={
                "event": "AUTOMATION_APPROVED",
                "intent_id": str(intent.intent_id),
                "strategy_id": intent.strategy_id,
                "instrument_id": intent.instrument_id,
                "actor_kind": actor_kind.value,
            },
            strategy_id=intent.strategy_id,
        )
        return True


def journal_path_journal(journal_path: str | Path) -> Journal:
    return Journal(Path(journal_path))
