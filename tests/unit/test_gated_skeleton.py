from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from nautilus_zerodte.actors.data_types import RegimeTagSnapshot, SessionPhaseSnapshot
from nautilus_zerodte.models.enums import RegimeTag
from nautilus_zerodte.strategies.gated_skeleton import (
    GatedSkeletonStrategy,
    GatedSkeletonStrategyConfig,
)


def test_evaluate_waits_for_regime_snapshot(tmp_path: Path) -> None:
    config = GatedSkeletonStrategyConfig(journal_path=str(tmp_path / "journal.jsonl"))
    strategy = GatedSkeletonStrategy(config)
    tick = MagicMock()

    strategy._on_session_phase(
        SessionPhaseSnapshot(
            allows_entry=True,
            session_phase="NORMAL",
            minutes_to_expiry=120,
            flatten_signal=False,
        )
    )
    strategy.on_quote_tick(tick)

    assert not strategy._evaluated

    strategy._on_regime_tag(RegimeTagSnapshot(regime_tag=RegimeTag.TREND.value))

    assert strategy._evaluated
    assert strategy._regime_tag == RegimeTag.TREND


def test_evaluate_waits_for_session_snapshot(tmp_path: Path) -> None:
    config = GatedSkeletonStrategyConfig(journal_path=str(tmp_path / "journal.jsonl"))
    strategy = GatedSkeletonStrategy(config)
    tick = MagicMock()

    strategy._on_regime_tag(RegimeTagSnapshot(regime_tag=RegimeTag.CHOP.value))
    strategy.on_quote_tick(tick)

    assert not strategy._evaluated

    strategy._on_session_phase(
        SessionPhaseSnapshot(
            allows_entry=True,
            session_phase="NORMAL",
            minutes_to_expiry=120,
            flatten_signal=False,
        )
    )

    assert strategy._evaluated
