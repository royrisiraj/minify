from typing import Literal

from pydantic import BaseModel


class ApplicationInfo(BaseModel):
    name: str
    version: str
    status: Literal["running"] = "running"


class Health(BaseModel):
    status: Literal["healthy"] = "healthy"
    service: Literal["minify-api"] = "minify-api"


class Readiness(BaseModel):
    status: Literal["ready"] = "ready"
    checks: dict[str, str]
