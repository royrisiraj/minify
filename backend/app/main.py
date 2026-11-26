import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.api.router import router
from app.core.config import Settings
from app.core.exceptions import ErrorResponse, register_exception_handlers
from app.core.logging import configure_logging
from app.database import Database
from app.middleware.body_limit import LinkBodyLimitMiddleware
from app.middleware.requests import RequestMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging("DEBUG" if settings.debug else settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Engine construction is lazy: a database outage must not prevent liveness.
        app.state.database = Database(settings)
        logging.getLogger("minify.lifecycle").debug("application_resources_initialized")
        try:
            yield
        finally:
            await run_in_threadpool(app.state.database.dispose)
            logging.getLogger("minify.lifecycle").debug("application_resources_released")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        # Never render exception tracebacks over HTTP, including development mode.
        debug=False,
        docs_url="/docs" if settings.expose_docs else None,
        redoc_url="/redoc" if settings.expose_docs else None,
        openapi_url="/openapi.json" if settings.expose_docs else None,
        swagger_ui_oauth2_redirect_url=None,
        responses={status: {"model": ErrorResponse} for status in (403, 404, 413, 422, 500, 503)},
    )
    app.state.settings = settings
    register_exception_handlers(app)
    app.include_router(router)
    app.add_middleware(LinkBodyLimitMiddleware)
    app.add_middleware(RequestMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(settings.frontend_url).rstrip("/")],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )
    return app
