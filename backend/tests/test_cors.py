def test_allowed_origin(client):
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in response.headers


def test_disallowed_origin(client):
    response = client.get("/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_preflight(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Accept",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-methods"] == "GET, POST"


def test_disallowed_preflight(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_configured_deployed_frontend_origin(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    configured = settings.model_copy(update={"frontend_url": "https://frontend.example.com/"})
    with TestClient(create_app(configured)) as client:
        response = client.get("/health", headers={"Origin": "https://frontend.example.com"})
        assert response.headers["access-control-allow-origin"] == "https://frontend.example.com"
