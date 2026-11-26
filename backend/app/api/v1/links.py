from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.links import LinkCreate, LinkRead
from app.services.links import create_link, creation_enabled

router = APIRouter()


def allow_creation(request: Request) -> None:
    creation_enabled(request.app.state.settings)


@router.post(
    "/links",
    status_code=201,
    response_model=LinkRead,
    dependencies=[Depends(allow_creation)],
    responses={
        403: {"description": "Anonymous creation disabled"},
        413: {"description": "Request body too large"},
        503: {"description": "Link service unavailable"},
    },
    tags=["links"],
)
def post_link(
    body: LinkCreate, request: Request, session: Annotated[Session, Depends(get_session)]
):
    return create_link(
        session, body.original_url, request.app.state.settings, request.state.request_id
    )
