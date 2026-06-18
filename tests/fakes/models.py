from __future__ import annotations

import numpy as np


class FakeSignalModel:
    def __init__(self, signal: float = 0.0) -> None:
        self.signal = signal
        self.calls: list[np.ndarray] = []

    def predict(self, features: np.ndarray) -> float:
        self.calls.append(np.asarray(features))
        return self.signal
