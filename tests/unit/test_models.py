from datetime import UTC, datetime

import numpy as np
import pytest

from data_pipeline.ingestion.synthetic import generate_bar_dataframe
from models.features.basic import compute_raw_features, transform_raw_features
from models.inference import SignalModel
from models.registry import load_model, save_model

jax = pytest.importorskip("jax", reason="requires the 'models' dependency group")

import jax.numpy as jnp  # noqa: E402

from models.architectures.mlp import init_mlp_params, mlp_forward  # noqa: E402
from models.jax_signal import JaxSignalModel  # noqa: E402

BARS = generate_bar_dataframe(start=datetime(2024, 1, 1, tzinfo=UTC), num_bars=200, seed=11)


class TestFeatures:
    def test_raw_feature_shape(self):
        raw = compute_raw_features(BARS)
        assert raw.shape == (200, 3)
        assert raw.dtype == np.float64

    def test_transform_shape_and_scale(self):
        x = transform_raw_features(compute_raw_features(BARS))
        assert x.shape == (200, 2)
        assert np.isfinite(x).all()
        assert np.abs(x).max() < 100  # scale-free, roughly O(1)

    def test_transform_rejects_wrong_width(self):
        with pytest.raises(ValueError, match="last dim"):
            transform_raw_features(np.zeros((5, 4)))


class TestMlp:
    def test_output_shape_dtype_and_range(self):
        params = init_mlp_params(jax.random.PRNGKey(0), [2, 16, 1])
        out = mlp_forward(params, jnp.zeros((7, 2)))
        assert out.shape == (7, 1)
        assert bool(jnp.all(jnp.abs(out) <= 1.0))

    def test_deterministic_per_seed(self):
        a = init_mlp_params(jax.random.PRNGKey(3), [2, 8, 1])
        b = init_mlp_params(jax.random.PRNGKey(3), [2, 8, 1])
        x = jnp.ones((1, 2))
        assert mlp_forward(a, x) == mlp_forward(b, x)


class TestRegistry:
    def test_save_load_roundtrip(self, tmp_path):
        params = init_mlp_params(jax.random.PRNGKey(1), [2, 4, 1])
        save_model(tmp_path / "m", params, metadata={"layer_sizes": [2, 4, 1]})

        loaded, metadata = load_model(tmp_path / "m")
        assert metadata["n_layers"] == 2
        assert metadata["layer_sizes"] == [2, 4, 1]
        for (w0, b0), (w1, b1) in zip(params, loaded, strict=True):
            np.testing.assert_array_equal(np.asarray(w0), w1)
            np.testing.assert_array_equal(np.asarray(b0), b1)


class TestJaxSignalModel:
    @pytest.fixture()
    def model(self, tmp_path):
        params = init_mlp_params(jax.random.PRNGKey(2), [2, 8, 1])
        save_model(tmp_path / "m", params, metadata={})
        return JaxSignalModel.from_artifact(tmp_path / "m")

    def test_satisfies_protocol(self, model):
        assert isinstance(model, SignalModel)

    def test_predict_contract(self, model):
        signal = model.predict(np.array([1.101, 1.100, 1.102]))
        assert isinstance(signal, float)
        assert -1.0 <= signal <= 1.0

    def test_rejects_bad_shape(self, model):
        with pytest.raises(ValueError, match="shape"):
            model.predict(np.zeros(5))
