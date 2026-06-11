"""Feature extraction shared by training (offline) and inference (in-strategy).

The raw feature contract matches what strategies can cheaply provide on each bar:
(ema_fast, ema_slow, close). `transform_raw_features` converts raw values into
scale-free model inputs; training and inference MUST use the same transform.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data_pipeline.schemas import validate_bar_dataframe

RAW_FEATURE_NAMES = ("ema_fast", "ema_slow", "close")

# Spread/momentum ratios are tiny for FX; scale to O(1) for stable training.
_SCALE = 1_000.0


def compute_raw_features(
    df: pd.DataFrame,
    fast_period: int = 10,
    slow_period: int = 30,
) -> np.ndarray:
    """Compute raw features (n_bars, 3) from a normalized bar dataframe."""
    validate_bar_dataframe(df)
    close = df["close"]
    ema_fast = close.ewm(span=fast_period, adjust=False).mean()
    ema_slow = close.ewm(span=slow_period, adjust=False).mean()
    return np.column_stack(
        [
            ema_fast.to_numpy(dtype=np.float64),
            ema_slow.to_numpy(dtype=np.float64),
            close.to_numpy(dtype=np.float64),
        ]
    )


def transform_raw_features(raw: np.ndarray) -> np.ndarray:
    """Map raw (..., 3) features to scale-free model inputs (..., 2).

    Outputs: [ema spread ratio, close-vs-slow momentum ratio], both scaled to O(1).
    """
    raw = np.asarray(raw, dtype=np.float64)
    if raw.shape[-1] != len(RAW_FEATURE_NAMES):
        raise ValueError(f"Expected last dim {len(RAW_FEATURE_NAMES)}, got {raw.shape[-1]}")
    ema_fast, ema_slow, close = raw[..., 0], raw[..., 1], raw[..., 2]
    spread = (ema_fast / ema_slow - 1.0) * _SCALE
    momentum = (close / ema_slow - 1.0) * _SCALE
    return np.stack([spread, momentum], axis=-1)
