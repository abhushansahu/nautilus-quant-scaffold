"""Gymnasium environment replaying historical/synthetic bars.

Built on the project's data layer (normalized bar dataframes from the synthetic
generator or the Parquet catalog) — deliberately NOT a second market simulator.
High-fidelity evaluation of trained policies belongs in a NautilusTrader backtest
via a `SignalModel` adapter.

Observation: window of log returns, shape (window,), float32.
Action: Discrete(3) — 0 = short, 1 = flat, 2 = long.
Reward: position * next log return - transaction cost on position changes.
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

from data_pipeline.schemas import validate_bar_dataframe


class MarketReplayEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        bars: pd.DataFrame,
        window: int = 32,
        cost_per_position_change: float = 1e-4,
    ) -> None:
        validate_bar_dataframe(bars)
        if len(bars) <= window + 1:
            raise ValueError(f"Need more than {window + 1} bars, got {len(bars)}")

        close = bars["close"].to_numpy(dtype=np.float64)
        self._log_returns = np.diff(np.log(close)).astype(np.float32)
        self._window = window
        self._cost = cost_per_position_change

        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(window,), dtype=np.float32)
        self.action_space = spaces.Discrete(3)

        self._t = window
        self._position = 0

    def _observation(self) -> np.ndarray:
        return self._log_returns[self._t - self._window : self._t]

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        self._t = self._window
        self._position = 0
        return self._observation(), {"position": self._position}

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action {action}")
        new_position = int(action) - 1  # {-1, 0, 1}

        next_return = float(self._log_returns[self._t])
        cost = self._cost * abs(new_position - self._position)
        reward = new_position * next_return - cost

        self._position = new_position
        self._t += 1
        terminated = self._t >= len(self._log_returns)
        return self._observation(), reward, terminated, False, {"position": self._position}
