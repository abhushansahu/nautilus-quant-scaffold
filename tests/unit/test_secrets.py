import pytest

from core.secrets import MissingSecretError, mask_secret, resolve_secret


class TestResolveSecret:
    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("TBT_TEST_SECRET", "abc123")
        assert resolve_secret("TBT_TEST_SECRET") == "abc123"

    def test_raises_when_required_and_missing(self, monkeypatch):
        monkeypatch.delenv("TBT_TEST_SECRET", raising=False)
        with pytest.raises(MissingSecretError) as exc_info:
            resolve_secret("TBT_TEST_SECRET")
        assert exc_info.value.env_var == "TBT_TEST_SECRET"

    def test_empty_value_treated_as_missing(self, monkeypatch):
        monkeypatch.setenv("TBT_TEST_SECRET", "")
        with pytest.raises(MissingSecretError):
            resolve_secret("TBT_TEST_SECRET")

    def test_optional_secret_returns_none(self, monkeypatch):
        monkeypatch.delenv("TBT_TEST_SECRET", raising=False)
        assert resolve_secret("TBT_TEST_SECRET", required=False) is None


class TestMaskSecret:
    def test_long_secret_keeps_edges_only(self):
        masked = mask_secret("sk-live-abcdef123456")
        assert masked.startswith("sk")
        assert masked.endswith("56")
        assert "abcdef" not in masked
        assert len(masked) == len("sk-live-abcdef123456")

    def test_short_secret_fully_masked(self):
        assert mask_secret("abc123") == "******"
