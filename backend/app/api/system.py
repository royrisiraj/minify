from fastapi import APIRouter, Request

from app.core.exceptions import error_response
from app.core.logging import log_failure
from app.schemas.health import ApplicationInfo, Health, Readiness

router = APIRouter(tags=["system"])


@router.get("/", response_model=ApplicationInfo)
def root(request: Request):
    settings = request.app.state.settings
    return ApplicationInfo(name=settings.app_name, version=settings.app_version)


@router.get("/health", response_model=Health)
def health():
    return Health()


@router.get("/ready", response_model=Readiness, responses={503: {"description": "Not ready"}})
def ready(request: Request):
    # A synchronous route runs database I/O in FastAPI's worker thread pool.
    try:
        request.app.state.database.check_connection()
    except Exception as error:
        log_failure("database_unavailable", error)
        return error_response(503, "NOT_READY", "The service is not ready.")
    return Readiness(checks={"database": "connected"})
