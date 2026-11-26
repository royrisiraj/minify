import asyncio

import pytest

from app.core.constants import MAX_REQUEST_BYTES
from app.middleware.body_limit import LinkBodyLimitMiddleware


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"1")]])
def test_stream_limit_ignores_declared_length(headers):
    async def exercise():
        chunks = iter(
            [
                {"type": "http.request", "body": b"x" * 16000, "more_body": True},
                {"type": "http.request", "body": b"x" * 16000, "more_body": True},
                {"type": "http.request", "body": b"x" * 1000, "more_body": True},
            ]
        )
        sent = []

        async def receive():
            return next(chunks)

        async def send(message):
            sent.append(message)

        async def downstream(*_args):
            pytest.fail("Oversized stream must not reach persistence")

        scope = {"type": "http", "method": "POST", "path": "/api/v1/links", "headers": headers}
        await LinkBodyLimitMiddleware(downstream)(scope, receive, send)
        assert sent[0]["status"] == 413
        assert b"REQUEST_TOO_LARGE" in sent[1]["body"]

    asyncio.run(exercise())


def test_stream_at_limit_replayed_exactly():
    async def exercise():
        payload = b"x" * MAX_REQUEST_BYTES
        messages = iter(
            [
                {"type": "http.request", "body": payload[:1000], "more_body": True},
                {"type": "http.request", "body": payload[1000:], "more_body": False},
            ]
        )

        async def receive():
            return next(messages)

        async def downstream(scope, replay, send):
            message = await replay()
            assert message["body"] == payload and not message["more_body"]

        await LinkBodyLimitMiddleware(downstream)(
            {"type": "http", "method": "POST", "path": "/api/v1/links"}, receive, None
        )

    asyncio.run(exercise())
