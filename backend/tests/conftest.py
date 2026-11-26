import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.database import Database
from app.main import create_app


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)


@pytest.fixture
def settings():
    return Settings(_env_file=None, app_env="testing")


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def migration_database(monkeypatch):
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated PostgreSQL database ending in _test")
    url = make_url(value).set(drivername="postgresql+psycopg")
    if not url.database or not url.database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name an isolated database ending in _test")
    # Each test owns a new database. No truncation or downgrade of an existing database.
    name = f"minify_{uuid4().hex}_test"
    admin = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True
    )
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    test_url = url.set(database=name).render_as_string(hide_password=False)
    settings = Settings(_env_file=None, app_env="testing", database_url=test_url)
    db = Database(settings)
    monkeypatch.setenv("DATABASE_URL", test_url)
    monkeypatch.setenv("APP_ENV", "testing")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        yield db, settings, config
    finally:
        db.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


@pytest.fixture
def link_database(migration_database):
    db, settings, config = migration_database
    command.upgrade(config, "head")
    return db, settings
