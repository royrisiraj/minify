"""Exercise the actual local Compose API and verify durable link persistence."""

import argparse
import errno
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from time import monotonic, sleep
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, body=None, *, timeout=10):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        return urllib.request.build_opener(NoRedirect).open(req, timeout=timeout)
    except urllib.error.HTTPError as response:
        return response


def transient_connection(error):
    return isinstance(error, (ConnectionError, TimeoutError)) or (
        isinstance(error, OSError)
        and error.errno
        in {
            errno.ECONNRESET,
            errno.ECONNREFUSED,
            errno.ECONNABORTED,
            errno.ETIMEDOUT,
            errno.EHOSTUNREACH,
            errno.ENETUNREACH,
        }
    )


def wait_ready(url, *, expected_status=200, timeout=30, attempt_timeout=3, interval=0.5):
    """Retry safe startup GETs only; business requests/assertions are never retried."""
    if min(timeout, attempt_timeout, interval) <= 0:
        raise ValueError("Readiness timeouts and polling interval must be positive")
    deadline = monotonic() + timeout
    last_error = None
    while (remaining := deadline - monotonic()) > 0:
        try:
            with request(url, timeout=min(attempt_timeout, remaining)) as response:
                if response.status == expected_status:
                    return
                if response.status not in {408, 429, 500, 502, 503, 504}:
                    raise RuntimeError(
                        f"Readiness {url}: expected HTTP {expected_status}, got {response.status}"
                    )
                last_error = RuntimeError(f"HTTP {response.status}")
        except urllib.error.URLError as error:
            if not transient_connection(error.reason):
                raise
            last_error = error
        except OSError as error:
            if not transient_connection(error):
                raise
            last_error = error
        remaining = deadline - monotonic()
        if remaining > 0:
            sleep(min(interval, remaining))
    raise RuntimeError(
        f"Readiness deadline ({timeout}s) exhausted for {url}; "
        f"expected HTTP {expected_status}; last failure: {last_error}"
    ) from last_error


def verify_database(link, project):
    # Parameters are passed separately; do not interpolate a URL or UUID into SQL.
    program = (
        "import json,sys; from uuid import UUID; from sqlalchemy import text; "
        "from app.core.config import Settings; from app.database import Database; "
        "from app.models import Link; db=Database(Settings()); "
        "session=db.sessions(); row=session.get(Link, UUID(sys.argv[1])); "
        "assert row is not None; "
        "assert session.scalar(text('SELECT version_num FROM alembic_version'))=='0002_links'; "
        "print(json.dumps({'short_code': row.short_code, 'original_url': row.original_url})); "
        "session.close(); db.dispose()"
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            project,
            "exec",
            "-T",
            "backend",
            "python",
            "-c",
            program,
            link["id"],
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == {key: link[key] for key in ("short_code", "original_url")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "verify"])
    parser.add_argument("--state", type=Path, default=ROOT / ".local" / "stack-link.json")
    parser.add_argument("--project", default=os.environ.get("COMPOSE_PROJECT_NAME", "minify"))
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--web", default="http://localhost:5173")
    args = parser.parse_args()
    for origin in (args.api, args.web):
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1"}
            or parsed.path
        ):
            parser.error("Verification targets must be plain local HTTP origins")
    wait_ready(args.api + "/health")
    wait_ready(args.api + "/ready")
    wait_ready(args.web)
    if args.action == "create":
        destination = (
            f"https://example.com/Verify%2FCase?first=1&first=2&probe={uuid4().hex}#section"
        )
        with request(args.api + "/api/v1/links", {"original_url": destination}) as response:
            assert response.status == 201
            link = json.load(response)
        assert re.fullmatch("[0-9A-Za-z]{7}", link["short_code"])
        assert link["short_url"] == args.api + "/" + link["short_code"]
        assert link["original_url"] == destination
        args.state.parent.mkdir(parents=True, exist_ok=True)
        args.state.write_text(json.dumps(link), encoding="utf-8")
    else:
        link = json.loads(args.state.read_text(encoding="utf-8"))
    verify_database(link, args.project)
    with request(args.api + "/" + link["short_code"]) as redirect:
        assert redirect.status == 302
        assert redirect.headers["Location"] == link["original_url"]
        assert redirect.headers["Cache-Control"] == "no-store"
    print(f"PASS: {args.action}; actual row, migration head, HTTP 302 and exact Location verified")


if __name__ == "__main__":
    main()
