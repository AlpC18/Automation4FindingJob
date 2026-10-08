from backend.app.core.config import (
    settings,
    _env_bool,
    _env_int,
    _env_float,
    _csv,
    production_config_issues,
)


def test_default_settings():
    """Verify default application settings are properly loaded."""
    assert settings.PROJECT_NAME == "Autonomous Career Agent Engine"
    assert settings.API_V1_PREFIX == "/api"
    assert isinstance(settings.scraper_platforms, list)
    assert len(settings.scraper_platforms) > 0


def test_env_helpers():
    """Test helper functions for boolean, integer, float and csv parsing."""
    # Boolean parsing
    assert _env_bool("NON_EXISTENT_VAR", default=True) is True
    assert _env_bool("NON_EXISTENT_VAR", default=False) is False

    # Integer parsing
    assert _env_int("NON_EXISTENT_VAR", default=42) == 42

    # Float parsing
    assert _env_float("NON_EXISTENT_VAR", default=3.14) == 3.14

    # CSV parsing
    parsed = _csv("item1, item2 , item3")
    assert parsed == ["item1", "item2", "item3"]
    assert _csv("") == []


def test_public_runtime_config_does_not_leak_secrets():
    """Verify that public runtime configuration never includes secrets."""
    config = settings.public_runtime_config()
    assert isinstance(config, dict)
    
    serialized = str(config).lower()
    # Check that private tokens or passwords are not present in public config
    assert "password" not in serialized
    assert "secret" not in serialized
    assert "token" not in serialized
    assert "api_key" not in serialized
