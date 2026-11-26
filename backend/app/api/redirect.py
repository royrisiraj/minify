from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_session
from app.services.links import resolve_link

router = APIRouter()


@router.get(
    "/{short_code}",
    response_class=RedirectResponse,
    status_code=302,
    responses={
        302: {
            "description": "Temporary redirect",
            "headers": {
                "Location": {"schema": {"type": "string"}, "description": "Stored destination"},
                "Cache-Control": {"schema": {"type": "string"}, "description": "no-store"},
            },
        },
        404: {"description": "Unknown, malformed or inactive link"},
        503: {"description": "Database unavailable"},
    },
    tags=["links"],
)
def redirect_link(
    short_code: str, request: Request, session: Annotated[Session, Depends(get_session)]
):
    destination = resolve_link(
        session, short_code, request.app.state.settings, request.state.request_id
    )
    return RedirectResponse(destination, status_code=302, headers={"Cache-Control": "no-store"})
