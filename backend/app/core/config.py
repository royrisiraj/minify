from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Precedence: constructor overrides > process environment > backend/.env > defaults."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    app_name: str = Field(default="Minify", min_length=1, max_length=100)
    app_version: str = Field(default="0.1.0", min_length=1, max_length=40)
    app_env: Literal["development", "testing", "staging", "production"] = "development"
    debug: bool = False
    host: str = Field(default="0.0.0.0", min_length=1)
    port: int = Field(default=8000, ge=1, le=65535)
    database_url: SecretStr = Field(
        default=SecretStr("postgresql+psycopg://minify:minify@localhost:5432/minify"),
        repr=False,
    )
    base_url: HttpUrl = HttpUrl("http://localhost:8000")
    frontend_url: HttpUrl = HttpUrl("http://localhost:5173")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    docs_enabled: bool | None = None
    database_timeout_seconds: int = Field(default=3, ge=1, le=10)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            if (
                url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}
                or not url.host
                or not url.database
            ):
                raise ValueError
            # Only the psycopg 3 synchronous driver is supported, including managed-provider DSNs.
            return SecretStr(
                url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
            )
        except (ArgumentError, ValueError):
            raise ValueError("DATABASE_URL must be a valid PostgreSQL connection URL") from None

    @field_validator("base_url", "frontend_url")
    @classmethod
    def validate_origin(cls, value: HttpUrl) -> HttpUrl:
        if value.username or value.password or value.query or value.fragment or value.path != "/":
            raise ValueError("Use an HTTP(S) origin without credentials, path, query, or fragment")
        return value

    @model_validator(mode="after")
    def validate_protected_environment(self) -> "Settings":
        if self.app_env in {"staging", "production"}:
            required = {"database_url", "base_url", "frontend_url"}
            if not required.issubset(self.model_fields_set):
                raise ValueError("Staging/production require DATABASE_URL, BASE_URL, FRONTEND_URL")
            if self.debug:
                raise ValueError("Debug mode is forbidden in staging/production")
            if self.base_url.scheme != "https" or self.frontend_url.scheme != "https":
                raise ValueError("Staging/production public origins must use HTTPS")
            url = make_url(self.database_url.get_secret_value())
            if (
                not url.password
                or url.password == "minify"
                or url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}
            ):
                raise ValueError(
                    "Staging/production require non-example credentials and database TLS"
                )
        return self

    @property
    def expose_docs(self) -> bool:
        if self.docs_enabled is not None:
            return self.docs_enabled
        return self.app_env in {"development", "testing"}
