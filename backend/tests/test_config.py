import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_precedence(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("APP_NAME=File name\nPORT=8080\n", encoding="utf-8")
    monkeypatch.setenv("APP_NAME", "Environment name")
    assert Settings(_env_file=env_file).app_name == "Environment name"
    assert Settings(_env_file=env_file, app_name="Explicit name").app_name == "Explicit name"
    assert Settings(_env_file=env_file).port == 8080
    monkeypatch.delenv("APP_NAME")
    assert Settings(_env_file=env_file).app_name == "File name"


@pytest.mark.parametrize(
    "override",
    [
        {"port": 0},
        {"port": 65536},
        {"app_env": "unknown"},
        {"database_url": "sqlite:///:memory:"},
        {"database_url": "not-a-url"},
        {"frontend_url": "https://example.com/path"},
        {"frontend_url": "https://user:password@example.com"},
        {"frontend_url": "*"},
        {"database_timeout_seconds": 0},
        {"log_level": "TRACE"},
    ],
)
def test_invalid_configuration_rejected(override):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **override)


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_protected_environment_requires_explicit_settings(environment):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env=environment)


def production_settings(**overrides):
    values = {
        "app_env": "production",
        "database_url": "postgresql://account:test-only-value@db.example.com/minify?sslmode=require",
        "base_url": "https://api.example.com",
        "frontend_url": "https://minify.example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_defaults_and_provider_url_normalization():
    settings = production_settings()
    assert not settings.expose_docs
    assert not settings.debug
    assert "postgresql+psycopg://" in settings.database_url.get_secret_value()
    assert "test-only-value" not in repr(settings)
    assert "test-only-value" not in settings.model_dump_json()


@pytest.mark.parametrize(
    "override",
    [
        {"debug": True},
        {"frontend_url": "http://example.com"},
        {"database_url": "postgresql://account:example@db.example.com/minify"},
        {"database_url": "postgresql://minify:minify@db.example.com/minify?sslmode=require"},
    ],
)
def test_unsafe_production_configuration_rejected(override):
    with pytest.raises(ValidationError):
        production_settings(**override)


def test_invalid_secret_not_exposed_in_validation_string():
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url="invalid-private-secret")
    assert "invalid-private-secret" not in str(error.value)
