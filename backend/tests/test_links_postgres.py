from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.exc import DataError, IntegrityError

from app.core.exceptions import AppError
from app.database import Base
from app.main import create_app
from app.models import Link
from app.repositories.links import insert_candidate
from app.services.links import create_link, resolve_link

pytestmark = pytest.mark.integration


def test_fresh_migration_metadata_and_isolated_downgrade(migration_database):
    db, _, config = migration_database
    command.upgrade(config, "head")
    with db.engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002_links"
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        constraints = inspect(connection).get_unique_constraints("links")
        assert any(c["name"] == "uq_links_short_code" for c in constraints)
        assert not inspect(connection).get_indexes("links") or all(
            i["unique"] for i in inspect(connection).get_indexes("links")
        )
    command.downgrade(config, "0001_foundation")
    with db.engine.connect() as connection:
        assert not inspect(connection).has_table("links")
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_actual_persistence_timestamps_duplicate_destinations_and_sessions(link_database):
    db, settings = link_database
    with db.sessions() as session:
        first = create_link(session, "https://example.com/Case%2F?q=a&q=b#frag", settings)
        second = create_link(session, first.original_url, settings)
        assert first.id != second.id and first.short_code != second.short_code
    with db.sessions() as session:
        row = session.get(Link, first.id)
        assert row is not None and row.created_at.utcoffset().total_seconds() == 0
        assert row.updated_at == row.created_at
        assert resolve_link(session, first.short_code, settings) == first.original_url
        session.execute(update(Link).where(Link.id == first.id).values(is_active=False))
        session.commit()
        session.expire_all()
        assert session.get(Link, first.id).updated_at >= row.created_at
        with pytest.raises(AppError, match="LINK_NOT_FOUND"):
            resolve_link(session, first.short_code, settings)
    assert db.engine.pool.checkedout() == 0


def test_actual_collision_exhaustion_and_rollback(link_database):
    db, settings = link_database
    with db.sessions() as session:
        with patch("app.services.links.generate_code", return_value="AAAAAAA"):
            first = create_link(session, "https://example.com/first", settings)
            with pytest.raises(AppError, match="SHORT_CODE_GENERATION_EXHAUSTED"):
                create_link(session, "https://example.com/second", settings)
        with patch("app.services.links.generate_code", side_effect=["AAAAAAA", "BBBBBBB"]):
            second = create_link(session, "https://example.com/second", settings)
        assert second.short_code == "BBBBBBB"
        assert session.get(Link, first.id).original_url == first.original_url
        assert session.scalar(select(func.count()).select_from(Link)) == 2


def test_actual_uniqueness_case_and_invalid_constraints(link_database):
    db, _ = link_database
    with db.sessions() as session:
        assert insert_candidate(session, "https://example.com", "AbCd123") is not None
        assert insert_candidate(session, "https://example.com", "abcd123") is not None
        session.commit()
        assert insert_candidate(session, "https://example.com", "AbCd123") is None
        session.rollback()
        for code in ("123456", "12345678", "abc-de!", "éabcdef"):
            with pytest.raises((IntegrityError, DataError)):
                session.add(Link(original_url="https://example.com", short_code=code))
                session.commit()
            session.rollback()
        with pytest.raises(IntegrityError):
            session.add(Link(original_url=None, short_code="Valid12"))
            session.commit()
        session.rollback()
        assert session.scalar(select(func.count()).select_from(Link)) == 2


def test_actual_concurrent_collision_race(link_database):
    db, settings = link_database
    workers = 8
    barrier = Barrier(workers)
    state = local()

    def candidate():
        if not getattr(state, "attempted", False):
            state.attempted = True
            barrier.wait(timeout=15)
            return "Race123"
        return uuid4().hex[:7]

    def create(_):
        with db.sessions() as session:
            return create_link(session, "https://example.com/concurrent", settings)

    with (
        patch("app.services.links.generate_code", side_effect=candidate),
        ThreadPoolExecutor(max_workers=workers) as executor,
    ):
        responses = list(executor.map(create, range(workers)))
    codes = {response.short_code for response in responses}
    assert len(codes) == workers and "Race123" in codes
    with db.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Link)) == workers
        for response in responses:
            assert resolve_link(session, response.short_code, settings) == response.original_url
    assert db.engine.pool.checkedout() == 0


def test_actual_api_commit_visibility_and_safe_logs(link_database, caplog):
    db, settings = link_database
    sensitive = "https://example.com/path?token=private-token#private-fragment"
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/links", json={"original_url": sensitive})
        assert response.status_code == 201
        body = response.json()
        with db.sessions() as session:
            assert session.get(Link, body["id"]).original_url == sensitive
        redirect = client.get(f"/{body['short_code']}", follow_redirects=False)
        assert redirect.status_code == 302 and redirect.headers["Location"] == sensitive
        assert client.get("/zzzzzzz", follow_redirects=False).status_code == 404
        assert client.get("/ready").status_code == 200
    assert "private-token" not in caplog.text and "private-fragment" not in caplog.text
