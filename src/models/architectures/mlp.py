"""Minimal pure-JAX MLP with a tanh head (signal in [-1, 1]).

Params are a list of (weights, bias) tuples — trivially serializable by
`models.registry`. Requires the `models` dependency group (jax).
"""

from __future__ import annotations

import jax
import jax.numpy as jnp

MlpParams = list[tuple[jax.Array, jax.Array]]


def init_mlp_params(key: jax.Array, layer_sizes: list[int]) -> MlpParams:
    """He-initialized params for layers [in, hidden..., out]."""
    params: MlpParams = []
    keys = jax.random.split(key, len(layer_sizes) - 1)
    for k, n_in, n_out in zip(keys, layer_sizes[:-1], layer_sizes[1:], strict=True):
        w = jax.random.normal(k, (n_in, n_out)) * jnp.sqrt(2.0 / n_in)
        b = jnp.zeros((n_out,))
        params.append((w, b))
    return params


def mlp_forward(params: MlpParams, x: jax.Array) -> jax.Array:
    """Forward pass; final layer squashed with tanh. x shape (..., n_in) -> (..., n_out)."""
    for w, b in params[:-1]:
        x = jnp.tanh(x @ w + b)
    w, b = params[-1]
    return jnp.tanh(x @ w + b)
