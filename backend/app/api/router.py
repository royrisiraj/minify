from fastapi import APIRouter

from app.api import system
from app.api.v1 import router as v1_router

router = APIRouter()
router.include_router(system.router)
router.include_router(v1_router)

# First path segments reserved for future aliases, even when documentation is disabled.
RESERVED_PATHS = frozenset({"", "health", "ready", "docs", "redoc", "openapi.json", "api"})
