import pytest
from pydantic import ValidationError

from t212.config import Settings, get_settings


def make_settings(**overrides: object) -> Settings:
    """Construct Settings directly without reading .env, for testing."""
    defaults = {"t212_api_key": "test-key-123"}
    return Settings.model_validate({**defaults, **overrides})


def test_defaults():
    s = make_settings()
    assert s.paper_mode is True
    assert s.trading_enabled is True
    assert s.max_order_value == 100.0
    assert s.log_level == "INFO"
    assert s.api_base_url == "https://live.trading212.com/api/v0"


def test_paper_mode_can_be_disabled():
    s = make_settings(paper_mode=False)
    assert s.paper_mode is False


def test_max_order_value_must_be_positive():
    with pytest.raises(ValidationError, match="max_order_value must be positive"):
        make_settings(max_order_value=0)

    with pytest.raises(ValidationError, match="max_order_value must be positive"):
        make_settings(max_order_value=-50)


def test_log_level_normalised_to_upper():
    s = make_settings(log_level="debug")
    assert s.log_level == "DEBUG"


def test_invalid_log_level():
    with pytest.raises(ValidationError, match="log_level must be one of"):
        make_settings(log_level="VERBOSE")


def test_api_key_required():
    with pytest.raises(ValidationError):
        Settings.model_validate({})


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("T212_API_KEY", "cached-key")
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
    get_settings.cache_clear()
