from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.router import RESERVED_PATHS
from app.core.config import Settings
from app.main import create_app


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"name": "Minify", "version": "0.1.0", "status": "running"}
    assert len(response.headers["X-Request-ID"]) == 32


def test_liveness_never_accesses_database(client):
    with patch.object(client.app.state.database, "check_connection") as check:
        assert client.get("/health").json() == {"status": "healthy", "service": "minify-api"}
        check.assert_not_called()


def test_ready_success(client):
    with patch.object(client.app.state.database, "check_connection") as check:
        response = client.get("/ready")
        check.assert_called_once()
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "connected"}}


def test_ready_failure_is_safe_and_liveness_survives(client):
    with patch.object(
        client.app.state.database, "check_connection", side_effect=RuntimeError("private-password")
    ):
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "NOT_READY"
        assert "private-password" not in response.text
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_documentation_enabled(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_documentation_can_be_disabled(path):
    with TestClient(create_app(Settings(_env_file=None, docs_enabled=False))) as client:
        assert client.get(path).status_code == 404


def test_versioned_links_and_reserved_operational_paths(client):
    assert client.get("/api/v1/health").status_code == 404
    assert client.post("/api/v1/links", json={}).status_code == 422
    assert {"health", "ready", "api", "docs", "redoc", "openapi.json"} <= RESERVED_PATHS


def test_lifespan_disposes_engine(app):
    with patch("app.database.Database.dispose") as dispose:
        with TestClient(app):
            dispose.assert_not_called()
        dispose.assert_called_once()
