"""RL algorithm implementations (stub).

Add JAX-based training loops here (e.g. PPO/DQN over `MarketReplayEnv`).
Conventions:
- Seeded randomness everywhere (jax.random.PRNGKey from config).
- Save trained policies through `models.registry` so strategies can load them
  via a `SignalModel` adapter — policies never touch the trading engine directly.
"""
