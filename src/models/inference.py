"""The inference contract between models and strategies.

Strategies depend only on this protocol; concrete models (JAX, RL policies, ...)
are injected by the factory layer. Models receive plain numpy feature arrays and
return signals — they never see venue clients, order objects, or secrets.

This module must stay importable without the `models` dependency group (no JAX imports).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class SignalModel(Protocol):
    """Maps a feature vector to a directional signal in [-1.0, 1.0].

    -1.0 = max conviction short, 0.0 = flat/no edge, 1.0 = max conviction long.
    """

    def predict(self, features: np.ndarray) -> float:
        """Return a signal for a single observation of shape (n_features,)."""
        ...
