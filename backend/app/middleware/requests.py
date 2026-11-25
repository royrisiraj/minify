import logging
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import error_response
from app.core.logging import log_failure


class RequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = uuid4().hex
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception as error:
            log_failure(f"request_failed request_id={request_id}", error)
            response = error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")
        response.headers["X-Request-ID"] = request_id
        # Avoid logging URLs, query strings, request bodies, or sensitive headers.
        logging.getLogger("minify.requests").info(
            "request_completed request_id=%s status=%s duration_ms=%.1f",
            request_id,
            response.status_code,
            (perf_counter() - started) * 1000,
        )
        return response
