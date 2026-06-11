"""Seeded offline training for the demo MLP signal model.

Supervised objective: predict the direction (tanh-squashed sign) of the next bar's
return from the current scale-free features. Heavy training never runs in live
trading; only the serialized artifact is deployed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import optax

from data_pipeline.ingestion.synthetic import generate_bar_dataframe
from models.architectures.mlp import init_mlp_params, mlp_forward
from models.features.basic import RAW_FEATURE_NAMES, compute_raw_features, transform_raw_features
from models.registry import save_model


@dataclass(frozen=True)
class TrainResult:
    artifact_dir: Path
    final_loss: float
    n_samples: int


def build_dataset(
    seed: int,
    num_bars: int = 5000,
    fast_period: int = 10,
    slow_period: int = 30,
) -> tuple[np.ndarray, np.ndarray]:
    """Features X (n, 2) and targets y (n,) = sign of next-bar return."""
    df = generate_bar_dataframe(
        start=datetime(2024, 1, 1, tzinfo=UTC), num_bars=num_bars, seed=seed
    )
    raw = compute_raw_features(df, fast_period=fast_period, slow_period=slow_period)
    x = transform_raw_features(raw)[:-1]
    next_returns = np.diff(np.log(df["close"].to_numpy()))
    y = np.sign(next_returns)
    return x, y


def train(
    seed: int = 0,
    layer_sizes: tuple[int, ...] = (2, 16, 1),
    num_steps: int = 500,
    learning_rate: float = 1e-3,
    artifact_dir: Path = Path("artifacts/mlp_signal"),
    num_bars: int = 5000,
) -> TrainResult:
    x_np, y_np = build_dataset(seed=seed, num_bars=num_bars)
    x, y = jnp.asarray(x_np), jnp.asarray(y_np)

    params = init_mlp_params(jax.random.PRNGKey(seed), list(layer_sizes))
    optimizer = optax.adam(learning_rate)
    opt_state = optimizer.init(params)

    def loss_fn(p, xb, yb):
        pred = mlp_forward(p, xb)[..., 0]
        return jnp.mean((pred - yb) ** 2)

    @jax.jit
    def step(p, s, xb, yb):
        loss, grads = jax.value_and_grad(loss_fn)(p, xb, yb)
        updates, s = optimizer.update(grads, s)
        return optax.apply_updates(p, updates), s, loss

    loss = jnp.inf
    for _ in range(num_steps):
        params, opt_state, loss = step(params, opt_state, x, y)

    final_loss = float(loss)
    save_model(
        artifact_dir,
        params,
        metadata={
            "model": "mlp_signal",
            "layer_sizes": list(layer_sizes),
            "raw_features": list(RAW_FEATURE_NAMES),
            "seed": seed,
            "num_steps": num_steps,
            "learning_rate": learning_rate,
            "num_bars": num_bars,
            "final_loss": final_loss,
        },
    )
    return TrainResult(artifact_dir=artifact_dir, final_loss=final_loss, n_samples=len(x_np))
