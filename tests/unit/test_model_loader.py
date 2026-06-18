from pathlib import Path

import numpy as np
import pytest

from models.inference import SignalModel
from models.loader import (
    MODEL_LOADERS,
    UnknownModelLoaderError,
    load_signal_model,
    register_model_loader,
)


class _FakeSignalModel:
    def __init__(self, value: float) -> None:
        self.value = value

    def predict(self, features: np.ndarray) -> float:
        return self.value


class _FakeLoader:
    def __init__(self, value: float = 0.5) -> None:
        self.value = value
        self.loaded_paths: list[Path] = []

    def load(self, artifact_path: Path) -> SignalModel:
        self.loaded_paths.append(artifact_path)
        return _FakeSignalModel(self.value)


@pytest.fixture(autouse=True)
def _isolate_registry():
    saved = dict(MODEL_LOADERS)
    MODEL_LOADERS.clear()
    yield
    MODEL_LOADERS.clear()
    MODEL_LOADERS.update(saved)


class TestModelLoaderRegistry:
    def test_register_and_load(self, tmp_path):
        loader = _FakeLoader(0.75)
        register_model_loader("fake", loader)
        model = load_signal_model(tmp_path / "artifact", kind="fake")
        assert isinstance(model, SignalModel)
        assert model.predict(np.zeros(3)) == 0.75
        assert loader.loaded_paths == [tmp_path / "artifact"]

    def test_unknown_kind_raises(self, tmp_path):
        with pytest.raises(UnknownModelLoaderError, match="unknown_kind"):
            load_signal_model(tmp_path, kind="unknown_kind")

    def test_jax_loader_registers_lazily(self, tmp_path):
        pytest.importorskip("jax", reason="requires the 'models' dependency group")
        import jax

        from models.architectures.mlp import init_mlp_params
        from models.registry import save_model

        params = init_mlp_params(jax.random.PRNGKey(0), [2, 4, 1])
        save_model(tmp_path / "m", params, metadata={})
        model = load_signal_model(tmp_path / "m")
        assert isinstance(model, SignalModel)
        assert -1.0 <= model.predict(np.array([1.0, 1.0, 1.0])) <= 1.0

    def test_custom_loader_without_jax(self, tmp_path):
        register_model_loader("jax_mlp", _FakeLoader())
        model = load_signal_model(tmp_path / "m")
        assert model.predict(np.zeros(1)) == 0.5
