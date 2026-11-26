"""Exercise the actual local Compose API and verify durable link persistence."""

import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        return urllib.request.build_opener(NoRedirect).open(req, timeout=10)
    except urllib.error.HTTPError as response:
        return response


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
    assert request(args.api + "/health").status == 200
    assert request(args.api + "/ready").status == 200
    assert request(args.web).status == 200
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
