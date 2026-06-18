"""JAX implementation of the `SignalModel` protocol.

Loads a serialized MLP artifact (see `models.registry`) and serves predictions to
strategies. Requires the `models` dependency group (jax); `models.inference`
stays importable without it.
"""

from __future__ import annotations

from pathlib import Path

import jax.numpy as jnp
import numpy as np

from models.architectures.mlp import mlp_forward
from models.features.basic import RAW_FEATURE_NAMES, transform_raw_features
from models.registry import load_model


class JaxSignalModel:
    """Wraps a trained MLP: raw strategy features -> directional signal in [-1, 1]."""

    def __init__(self, params: list[tuple[np.ndarray, np.ndarray]]) -> None:
        self._params = [(jnp.asarray(w), jnp.asarray(b)) for w, b in params]

    @classmethod
    def from_artifact(cls, artifact_dir: Path | str) -> JaxSignalModel:
        params, _ = load_model(Path(artifact_dir))
        return cls(params)

    def predict(self, features: np.ndarray) -> float:
        features = np.asarray(features, dtype=np.float64)
        if features.shape != (len(RAW_FEATURE_NAMES),):
            raise ValueError(
                f"Expected features of shape ({len(RAW_FEATURE_NAMES)},) "
                f"{RAW_FEATURE_NAMES}, got {features.shape}"
            )
        x = jnp.asarray(transform_raw_features(features))
        signal = float(mlp_forward(self._params, x)[0])
        return max(-1.0, min(1.0, signal))


class JaxSignalModelLoader:
    def load(self, artifact_path: Path) -> JaxSignalModel:
        return JaxSignalModel.from_artifact(artifact_path)


def register_jax_model_loader() -> None:
    from models.loader import register_model_loader

    register_model_loader("jax_mlp", JaxSignalModelLoader())
