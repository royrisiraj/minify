from fastapi import APIRouter

from app.api import redirect, system
from app.api.v1 import router as v1_router
from app.core.constants import RESERVED_PATHS as RESERVED_PATHS

router = APIRouter()
router.include_router(system.router)
router.include_router(v1_router)
router.include_router(redirect.router)
