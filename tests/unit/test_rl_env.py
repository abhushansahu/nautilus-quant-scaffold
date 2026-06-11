from datetime import UTC, datetime

import numpy as np
import pytest

from data_pipeline.ingestion.synthetic import generate_bar_dataframe

pytest.importorskip("gymnasium", reason="requires the 'models' dependency group")

from models.rl.envs.market_env import MarketReplayEnv  # noqa: E402

BARS = generate_bar_dataframe(start=datetime(2024, 1, 1, tzinfo=UTC), num_bars=100, seed=9)


@pytest.fixture()
def env() -> MarketReplayEnv:
    return MarketReplayEnv(BARS, window=16)


class TestMarketReplayEnv:
    def test_reset_observation_contract(self, env):
        obs, info = env.reset(seed=0)
        assert obs.shape == (16,)
        assert obs.dtype == np.float32
        assert info["position"] == 0

    def test_step_contract(self, env):
        env.reset(seed=0)
        obs, reward, terminated, truncated, info = env.step(2)  # go long
        assert obs.shape == (16,)
        assert np.isfinite(reward)
        assert truncated is False
        assert info["position"] == 1

    def test_position_change_costs(self, env):
        env.reset(seed=0)
        # Going long then flipping short pays the transaction cost twice over.
        _, r_long, *_ = env.step(2)
        _, r_short, *_ = env.step(0)
        expected_return = float(env._log_returns[17])
        assert r_short == pytest.approx(-expected_return - 2 * env._cost)
        del r_long

    def test_episode_terminates_at_data_end(self, env):
        env.reset(seed=0)
        terminated = False
        steps = 0
        while not terminated:
            _, _, terminated, _, _ = env.step(1)
            steps += 1
        assert steps == 99 - 16  # n_returns - window

    def test_replay_is_deterministic(self):
        rewards = []
        for _ in range(2):
            env = MarketReplayEnv(BARS, window=16)
            env.reset(seed=123)
            total = 0.0
            for _ in range(20):
                _, reward, *_ = env.step(2)
                total += reward
            rewards.append(total)
        assert rewards[0] == rewards[1]

    def test_rejects_too_few_bars(self):
        small = generate_bar_dataframe(start=datetime(2024, 1, 1, tzinfo=UTC), num_bars=10, seed=1)
        with pytest.raises(ValueError, match="Need more than"):
            MarketReplayEnv(small, window=16)

    def test_rejects_invalid_action(self, env):
        env.reset(seed=0)
        with pytest.raises(ValueError, match="Invalid action"):
            env.step(5)
