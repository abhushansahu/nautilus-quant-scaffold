from pathlib import Path
from unittest.mock import MagicMock

from core.config import RiskSettings
from core.experiment import StrategySpec
from nt_ext.factories import build_strategy
from nt_ext.strategies.multi_asset.switcher import SwitcherStrategy
from nt_ext.strategies.signals import PositionState, SignalIntent

RISK = RiskSettings(max_notional_per_order=200_000, max_open_positions=1, max_drawdown_pct=0.5)


def _switcher_spec(state_path: Path) -> StrategySpec:
    return StrategySpec(
        key="switcher",
        instrument_id="EUR/USD.SIM",
        bar_type="EUR/USD.SIM-1-MINUTE-MID-EXTERNAL",
        params={
            "trade_size": 100_000,
            "reevaluate_every_bars": 1,
            "flatten_on_switch": False,
            "state_path": str(state_path),
            "candidates": [
                {
                    "key": "ema_cross",
                    "params": {
                        "name": "ema_fast",
                        "fast_period": 10,
                        "slow_period": 30,
                        "trade_size": 100_000,
                    },
                },
                {
                    "key": "ema_cross",
                    "params": {
                        "name": "ema_slow",
                        "fast_period": 20,
                        "slow_period": 50,
                        "trade_size": 100_000,
                    },
                },
            ],
        },
    )


class TestSwitcherStrategy:
    def test_builds_with_two_children(self):
        strategy = build_strategy(_switcher_spec(Path("/tmp/state.json")), risk=RISK)
        assert isinstance(strategy, SwitcherStrategy)
        assert set(strategy._children) == {"ema_fast", "ema_slow"}

    def test_switches_active_child_from_state(self, tmp_path):
        from core.active_strategy import ActiveStrategyState

        state_path = tmp_path / "active_strategy.json"
        ActiveStrategyState.write(
            suite="ema_eval",
            active_profile="ema_slow",
            metric="sharpe_ratio",
            metric_value=1.0,
            run_id="slow_1",
            path=state_path,
        )
        strategy = build_strategy(_switcher_spec(state_path), risk=RISK)
        strategy._refresh_active_child(force=True)
        assert strategy._active_profile == "ema_slow"
        assert strategy._active_child is strategy._children["ema_slow"]

    def test_delegates_on_signal_bar_to_active_child(self, tmp_path):
        from core.active_strategy import ActiveStrategyState

        state_path = tmp_path / "active_strategy.json"
        ActiveStrategyState.write(
            suite="ema_eval",
            active_profile="ema_fast",
            metric="sharpe_ratio",
            metric_value=1.0,
            run_id="fast_1",
            path=state_path,
        )
        strategy = build_strategy(_switcher_spec(state_path), risk=RISK)
        strategy._refresh_active_child(force=True)
        child = strategy._active_child
        assert child is not None
        child.evaluate = MagicMock(return_value=SignalIntent.NOOP)
        strategy._position_state = MagicMock(
            return_value=PositionState(is_net_long=False, is_net_short=False, is_flat=True)
        )
        bar = MagicMock()
        strategy.on_signal_bar(bar)
        child.evaluate.assert_called_once()
