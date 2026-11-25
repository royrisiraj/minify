from unittest.mock import patch

from fastapi import HTTPException


def test_http_error_preserves_status_and_headers(app, client):
    @app.get("/_test/http")
    def fail():
        raise HTTPException(401, "private-token", headers={"WWW-Authenticate": "Bearer"})

    response = client.get("/_test/http")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "HTTP_ERROR"
    assert "private-token" not in response.text


def test_validation_error_does_not_echo_input(app, client):
    @app.get("/_test/validation")
    def validate(count: int):
        return {"count": count}

    response = client.get("/_test/validation?count=private-input")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "private-input" not in response.text


def test_unexpected_error_safe_logs_and_cors(app, client):
    @app.get("/_test/error")
    def fail():
        raise RuntimeError("password=private-database-value")

    with patch("app.core.logging.logging.getLogger") as logger:
        response = client.get("/_test/error", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}
    }
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "X-Request-ID" in response.headers
    assert "private-database-value" not in response.text
    assert "private-database-value" not in str(logger.mock_calls)


def test_unknown_route_uses_error_contract(client):
    response = client.get("/missing")
    assert response.status_code == 404
    assert set(response.json()) == {"error"}
