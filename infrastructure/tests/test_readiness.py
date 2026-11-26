import importlib.util
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

import pytest

spec = importlib.util.spec_from_file_location(
    "verify_stack", Path(__file__).resolve().parents[1] / "verify_stack.py"
)
stack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stack)


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(stack, "monotonic", lambda: now[0])
    monkeypatch.setattr(stack, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


def response(status=200):
    result = MagicMock(status=status)
    result.__enter__.return_value = result
    return result


def test_immediate_success_closes_response(monkeypatch, clock):
    result = response()
    probe = MagicMock(return_value=result)
    monkeypatch.setattr(stack, "request", probe)
    stack.wait_ready("http://localhost")
    probe.assert_called_once_with("http://localhost", timeout=3)
    result.__exit__.assert_called_once()
    assert clock[0] == 0


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionResetError("reset"),
        ConnectionRefusedError("refused"),
        ConnectionAbortedError("aborted"),
        TimeoutError("timeout"),
        urllib.error.URLError(ConnectionRefusedError("refused")),
    ],
)
def test_transient_then_success(monkeypatch, clock, failure):
    probe = MagicMock(side_effect=[failure, response()])
    monkeypatch.setattr(stack, "request", probe)
    stack.wait_ready("http://localhost")
    assert probe.call_count == 2 and clock[0] == 0.5


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_temporary_http_then_success_closes_both(monkeypatch, clock, status):
    first, second = response(status), response()
    monkeypatch.setattr(stack, "request", MagicMock(side_effect=[first, second]))
    stack.wait_ready("http://localhost")
    first.__exit__.assert_called_once()
    second.__exit__.assert_called_once()


def test_persistent_failure_is_bounded_and_diagnostic(monkeypatch, clock):
    probe = MagicMock(side_effect=ConnectionResetError("reset"))
    monkeypatch.setattr(stack, "request", probe)
    with pytest.raises(RuntimeError, match="deadline.*last failure: reset"):
        stack.wait_ready("http://localhost", timeout=1, interval=0.6)
    assert clock[0] == 1 and probe.call_count == 2
    assert probe.call_args.kwargs["timeout"] == pytest.approx(0.4)


@pytest.mark.parametrize(
    "error",
    [
        ValueError("bug"),
        TypeError("bug"),
        urllib.error.URLError("unexpected reason"),
        OSError("bug"),
    ],
)
def test_unexpected_errors_propagate(monkeypatch, clock, error):
    probe = MagicMock(side_effect=error)
    monkeypatch.setattr(stack, "request", probe)
    with pytest.raises(type(error)):
        stack.wait_ready("http://localhost")
    assert probe.call_count == 1


def test_exact_expected_status_required(monkeypatch, clock):
    result = response(201)
    monkeypatch.setattr(stack, "request", MagicMock(return_value=result))
    with pytest.raises(RuntimeError, match="expected HTTP 200, got 201"):
        stack.wait_ready("http://localhost")
    result.__exit__.assert_called_once()


def test_creation_failure_is_not_retried(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sys.argv",
        ["verify_stack.py", "create", "--state", str(tmp_path / "link.json")],
    )
    monkeypatch.setattr(stack, "wait_ready", MagicMock())
    result = response(503)
    probe = MagicMock(return_value=result)
    monkeypatch.setattr(stack, "request", probe)
    with pytest.raises(AssertionError):
        stack.main()
    probe.assert_called_once()
    assert probe.call_args.args[1]["original_url"].startswith("https://example.com/")
    result.__exit__.assert_called_once()
