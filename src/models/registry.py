"""Model artifact registry: deterministic, dependency-light serialization.

An artifact directory contains:
    params.npz      flat numpy arrays named layer{i}_{w|b}
    metadata.json   layer sizes, feature contract, training info

Live trading loads only these artifacts — never training code.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

PARAMS_FILE = "params.npz"
METADATA_FILE = "metadata.json"

NumpyParams = list[tuple[np.ndarray, np.ndarray]]


def save_model(artifact_dir: Path, params: Any, metadata: dict[str, Any]) -> Path:
    """Persist MLP-style params (list of (w, b)) and metadata. Returns the artifact dir."""
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    arrays: dict[str, Any] = {}
    for i, (w, b) in enumerate(params):
        arrays[f"layer{i}_w"] = np.asarray(w)
        arrays[f"layer{i}_b"] = np.asarray(b)
    np.savez(artifact_dir / PARAMS_FILE, **arrays)

    full_metadata = {
        "saved_at": datetime.now(UTC).isoformat(),
        "n_layers": len(params),
        **metadata,
    }
    (artifact_dir / METADATA_FILE).write_text(json.dumps(full_metadata, indent=2, default=str))
    return artifact_dir


def load_model(artifact_dir: Path) -> tuple[NumpyParams, dict[str, Any]]:
    """Load params and metadata saved by `save_model`."""
    artifact_dir = Path(artifact_dir)
    metadata = json.loads((artifact_dir / METADATA_FILE).read_text())
    with np.load(artifact_dir / PARAMS_FILE) as data:
        params = [(data[f"layer{i}_w"], data[f"layer{i}_b"]) for i in range(metadata["n_layers"])]
    return params, metadata
