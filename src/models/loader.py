"""Model artifact loading registry.

Apps depend on `load_signal_model` rather than concrete model classes. Concrete
loaders register themselves (e.g. JAX MLP in `models.jax_signal`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from models.inference import SignalModel

MODEL_LOADERS: dict[str, ModelLoader] = {}
DEFAULT_MODEL_KIND = "jax_mlp"


class ModelLoader(Protocol):
    def load(self, artifact_path: Path) -> SignalModel: ...


class UnknownModelLoaderError(KeyError):
    def __init__(self, kind: str) -> None:
        super().__init__(
            f"Unknown model loader '{kind}'. Registered: {sorted(MODEL_LOADERS)}. "
            "Register loaders via register_model_loader()."
        )


def register_model_loader(kind: str, loader: ModelLoader) -> None:
    MODEL_LOADERS[kind] = loader


def _ensure_default_loaders() -> None:
    if DEFAULT_MODEL_KIND in MODEL_LOADERS:
        return
    try:
        from models.jax_signal import register_jax_model_loader

        register_jax_model_loader()
    except ImportError:
        pass


def load_signal_model(artifact_path: Path | str, kind: str | None = None) -> SignalModel:
    """Load a SignalModel from a serialized artifact directory."""
    _ensure_default_loaders()
    resolved_kind = kind or DEFAULT_MODEL_KIND
    if resolved_kind not in MODEL_LOADERS:
        raise UnknownModelLoaderError(resolved_kind)
    return MODEL_LOADERS[resolved_kind].load(Path(artifact_path))
