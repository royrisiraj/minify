import socket
from time import monotonic
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database import Database, get_session
from app.main import create_app


def test_engine_timeouts_and_pool_settings(settings):
    with patch("app.database.create_engine") as create:
        Database(settings)
    options = create.call_args.kwargs
    assert options["pool_pre_ping"]
    assert options["hide_parameters"]
    assert options["pool_timeout"] == 3
    assert options["connect_args"]["connect_timeout"] == 3
    assert "statement_timeout=3000" in options["connect_args"]["options"]


@pytest.mark.parametrize("failure", [False, True])
def test_session_dependency_closes_and_rolls_back(failure):
    session = MagicMock()
    sessions = MagicMock()
    sessions.return_value.__enter__.return_value = session
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(database=SimpleNamespace(sessions=sessions)))
    )
    dependency = get_session(request)
    assert next(dependency) is session
    if failure:
        with pytest.raises(RuntimeError):
            dependency.throw(RuntimeError("operation failed"))
        session.rollback.assert_called_once()
    else:
        dependency.close()
        session.commit.assert_not_called()
    sessions.return_value.__exit__.assert_called_once()


def test_real_connection_refusal_is_bounded_and_does_not_break_health():
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
        settings = Settings(
            _env_file=None,
            app_env="testing",
            database_timeout_seconds=1,
            database_url=f"postgresql+psycopg://test:test@127.0.0.1:{port}/minify_test",
        )
        with TestClient(create_app(settings)) as client:
            started = monotonic()
            assert client.get("/ready").status_code == 503
            assert monotonic() - started < 5
            assert client.get("/health").status_code == 200
