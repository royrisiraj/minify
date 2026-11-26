import os
from io import StringIO
from types import SimpleNamespace

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database import Database, get_session
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def postgres_settings():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL database ending in _test")
    url = make_url(value)
    if not url.database or not url.database.endswith("_test"):
        pytest.fail("Integration tests require a dedicated database name ending in _test")
    return Settings(_env_file=None, app_env="testing", database_url=value)


@pytest.fixture
def database(postgres_settings):
    database = Database(postgres_settings)
    yield database
    database.dispose()


def test_actual_postgres_connection(database):
    database.check_connection()
    with database.engine.connect() as connection:
        assert "PostgreSQL" in connection.scalar(text("SELECT version()"))


def test_session_dependency_releases_actual_connection(database):
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(database=database)))
    dependency = get_session(request)
    session = next(dependency)
    assert session.scalar(text("SELECT 1")) == 1
    dependency.close()
    assert database.engine.pool.checkedout() == 0


def test_actual_transaction_commit_and_rollback(database):
    with database.engine.connect() as connection, Session(bind=connection) as session:
        session.execute(text("CREATE TEMP TABLE phase01_probe (value integer)"))
        session.commit()
        session.execute(text("INSERT INTO phase01_probe VALUES (1)"))
        session.commit()
        session.execute(text("INSERT INTO phase01_probe VALUES (2)"))
        session.rollback()
        assert session.scalar(text("SELECT count(*) FROM phase01_probe")) == 1
        session.execute(text("DROP TABLE phase01_probe"))
        session.commit()


def test_actual_database_readiness(postgres_settings):
    with TestClient(create_app(postgres_settings)) as client:
        assert client.get("/ready").status_code == 200
        assert client.get("/health").status_code == 200


def test_actual_alembic_upgrade_current_heads(migration_database):
    database, _, config = migration_database
    output = StringIO()
    config.stdout = output
    # Independently retain the Phase 01 empty baseline assertion.
    command.upgrade(config, "0001_foundation")
    with database.engine.connect() as connection:
        assert set(
            connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            ).scalars()
        ) == {"alembic_version"}
    command.upgrade(config, "head")
    command.current(config)
    command.heads(config)
    assert output.getvalue().count("0002_links (head)") == 2
    with database.engine.connect() as connection:
        tables = (
            connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
            .scalars()
            .all()
        )
        assert set(tables) == {"alembic_version", "links"}
