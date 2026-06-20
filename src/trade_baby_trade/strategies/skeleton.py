from __future__ import annotations

from pathlib import Path

from nautilus_trader.config import StrategyConfig
from nautilus_trader.trading.strategy import Strategy

from trade_baby_trade.journal.service import Journal
from trade_baby_trade.models.enums import GateStage


class SkeletonZeroDteStrategyConfig(StrategyConfig, frozen=True):
    strategy_id: str = "skeleton-001"
    journal_path: str = "runs/latest.jsonl"
    underlying: str = "SPY.NYSE"


class SkeletonZeroDteStrategy(Strategy):
    """Phase 1 stub — journals lifecycle only; no subscriptions or orders."""

    def __init__(self, config: SkeletonZeroDteStrategyConfig) -> None:
        super().__init__(config)
        self._journal = Journal(Path(config.journal_path))
        self._strategy_id = config.strategy_id

    def on_start(self) -> None:
        self._journal.record(
            GateStage.LIFECYCLE,
            payload={"event": "STRATEGY_START", "underlying": self.config.underlying},
            strategy_id=self._strategy_id,
        )

    def on_stop(self) -> None:
        self._journal.record(
            GateStage.LIFECYCLE,
            payload={"event": "STRATEGY_STOP", "underlying": self.config.underlying},
            strategy_id=self._strategy_id,
        )
