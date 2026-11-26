from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.config import Settings
from app.core.constants import MAX_CREATION_ATTEMPTS, RESERVED_PATHS, usable_code
from app.core.exceptions import AppError
from app.database import get_session
from app.main import create_app
from app.repositories.links import find_link, insert_candidate
from app.services.links import create_link, generate_code, resolve_link


def stored(code="Ab12Zxy", url="https://example.com/Path%2F?q=a&q=b#Frag", active=True):
    return SimpleNamespace(
        id=uuid4(),
        original_url=url,
        short_code=code,
        is_active=active,
        created_at=datetime.now(UTC),
    )


def test_secure_generation_and_reserved():
    with patch("app.services.links.secrets.choice", return_value="A") as choice:
        assert generate_code() == "AAAAAAA"
        assert choice.call_count == 7
    codes = {generate_code() for _ in range(2000)}
    assert len(codes) == 2000
    assert all(usable_code(code) for code in codes)
    assert all(not usable_code(path) for path in RESERVED_PATHS)
    assert not usable_code("SWAGGER")
    assert not usable_code("Ab12xy\n")


def test_retry_then_commit_and_real_values(settings):
    session = MagicMock()
    row = stored()
    with (
        patch(
            "app.services.links.generate_code", side_effect=["Swagger", "AAAAAAA", row.short_code]
        ),
        patch("app.services.links.insert_candidate", side_effect=[None, row]) as insert,
    ):
        response = create_link(session, row.original_url, settings)
    assert insert.call_count == 2
    session.commit.assert_called_once()
    session.rollback.assert_not_called()
    assert response.id == row.id
    assert response.short_url == f"http://localhost:8000/{row.short_code}"
    assert response.expires_at is None


def test_collision_exhaustion_rolls_back(settings):
    session = MagicMock()
    with (
        patch("app.services.links.insert_candidate", return_value=None) as insert,
        pytest.raises(AppError, match="SHORT_CODE_GENERATION_EXHAUSTED"),
    ):
        create_link(session, "https://example.com", settings)
    assert insert.call_count == MAX_CREATION_ATTEMPTS
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


@pytest.mark.parametrize("where", ["insert", "commit"])
@pytest.mark.parametrize(
    "error, expected",
    [
        (OperationalError("sensitive SQL", {}, RuntimeError("password")), "DATABASE_UNAVAILABLE"),
        (IntegrityError("sensitive SQL", {}, RuntimeError("other integrity")), None),
        (RuntimeError("programming error"), None),
    ],
)
def test_other_errors_are_not_retried(settings, where, error, expected):
    session = MagicMock()
    if where == "commit":
        session.commit.side_effect = error
    with (
        patch(
            "app.services.links.insert_candidate",
            side_effect=error if where == "insert" else None,
            return_value=stored(),
        ) as insert,
        pytest.raises(AppError if expected else type(error)) as caught,
    ):
        create_link(session, "https://example.com", settings)
    if expected:
        assert caught.value.code == expected
    assert insert.call_count == 1
    session.rollback.assert_called_once()


def test_parameterized_statements():
    session = MagicMock()
    destination = "https://example.com/?q=';DROP%20TABLE%20links;--"
    insert_candidate(session, destination, "Ab12Zxy")
    statement = session.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert destination not in str(statement)
    assert destination in statement.params.values()
    assert "ON CONFLICT ON CONSTRAINT uq_links_short_code DO NOTHING" in str(statement)
    find_link(session, "x' OR 1=1")
    assert "x' OR 1=1" not in str(session.scalar.call_args.args[0])


@pytest.fixture
def link_client(settings):
    app = create_app(settings)
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, session


def test_creation_contract_and_untrusted_host(link_client):
    client, session = link_client
    row = stored()
    with patch("app.services.links.insert_candidate", return_value=row):
        response = client.post(
            "/api/v1/links",
            json={"original_url": row.original_url},
            headers={"Host": "evil.example", "X-Forwarded-Host": "evil.example"},
        )
    assert response.status_code == 201
    assert response.json() == {
        "id": str(row.id),
        "original_url": row.original_url,
        "short_code": row.short_code,
        "short_url": f"http://localhost:8000/{row.short_code}",
        "is_active": True,
        "created_at": row.created_at.isoformat().replace("+00:00", "Z"),
        "expires_at": None,
    }
    session.commit.assert_called_once()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"original_url": None},
        {"original_url": 12},
        {"original_url": ""},
        {"original_url": "x" * 4097},
        {"original_url": "https://example.com", "unknown": 1},
    ],
)
def test_bad_schema(client, body):
    response = client.post("/api/v1/links", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("field", ["custom_alias", "expires_at"])
def test_unsupported_fields(client, field):
    response = client.post(
        "/api/v1/links", json={"original_url": "https://example.com", field: "value"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FEATURE_NOT_SUPPORTED"


def test_body_limit_malformed_json_and_content_type(client):
    response = client.post(
        "/api/v1/links", content=b"x" * 33000, headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 413
    assert response.headers["X-Request-ID"]
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert client.post("/api/v1/links", content="{").status_code == 422
    assert (
        client.post(
            "/api/v1/links",
            content='{"original_url":"https://example.com"}',
            headers={"Content-Type": "text/plain"},
        ).status_code
        == 422
    )


@pytest.mark.parametrize("code", ["Ab12Zxy", "abcdefg"])
def test_redirect_exact_semantics_no_query_override(link_client, code):
    client, _ = link_client
    row = stored(code)
    with patch("app.services.links.find_link", return_value=row):
        response = client.get(f"/{code}?url=https://evil.example", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == row.original_url
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "code", ["x", "TOOLONG8", "abc-def", "éabcdef", "Swagger", "AAAAAA_", "unknown"]
)
def test_missing_codes(link_client, code):
    client, _ = link_client
    with patch("app.services.links.find_link", return_value=None):
        response = client.get(f"/{code}", follow_redirects=False)
    assert response.status_code == 404
    assert "Location" not in response.headers


@pytest.mark.parametrize(
    "row",
    [
        None,
        stored(active=False),
        stored(url="javascript:alert(1)"),
        stored(url="https://example.com/%0d%0aevil"),
    ],
)
def test_inactive_and_unsafe_stored_rows(settings, row):
    with (
        patch("app.services.links.find_link", return_value=row),
        pytest.raises(AppError, match="LINK_NOT_FOUND"),
    ):
        resolve_link(MagicMock(), "Ab12Zxy", settings)


@pytest.mark.parametrize("env", ["staging", "production"])
def test_protected_creation_fail_closed(env):
    settings = Settings(
        _env_file=None,
        app_env=env,
        database_url="postgresql://u:private@db.example/minify?sslmode=require",
        base_url="https://sho.rt",
        frontend_url="https://app.example.com",
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/links", json={"original_url": "https://example.com"})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CREATION_DISABLED"


def test_post_cors(client):
    response = client.options(
        "/api/v1/links",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "access-control-allow-credentials" not in response.headers


def test_openapi(client):
    schema = client.get("/openapi.json").json()
    assert "201" in schema["paths"]["/api/v1/links"]["post"]["responses"]
    assert "302" in schema["paths"]["/{short_code}"]["get"]["responses"]
    assert (
        schema["paths"]["/api/v1/links"]["post"]["responses"]["422"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        == "#/components/schemas/ErrorResponse"
    )
    assert (
        schema["components"]["schemas"]["LinkCreate"]["properties"]["custom_alias"]["type"]
        == "null"
    )
