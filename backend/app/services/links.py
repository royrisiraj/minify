import logging
import secrets

from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError, TimeoutError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.constants import (
    MAX_CREATION_ATTEMPTS,
    SHORT_CODE_ALPHABET,
    SHORT_CODE_LENGTH,
    usable_code,
)
from app.core.exceptions import AppError
from app.core.logging import log_failure
from app.repositories.links import find_link, insert_candidate
from app.schemas.links import LinkRead
from app.services.urls import validate_destination


def generate_code() -> str:
    return "".join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(SHORT_CODE_LENGTH))


def database_unavailable(error: Exception) -> bool:
    if isinstance(error, (OperationalError, InterfaceError, TimeoutError)):
        return True
    if isinstance(error, DBAPIError):
        state = getattr(error.orig, "sqlstate", "") or ""
        return (
            error.connection_invalidated
            or state.startswith(("08", "53"))
            or state in {"57P01", "57P02", "57P03"}
        )
    return False


def creation_enabled(settings: Settings) -> None:
    if settings.app_env not in {"development", "testing"}:
        raise AppError(
            403, "CREATION_DISABLED", "Anonymous link creation is disabled in this environment."
        )


def create_link(session: Session, value: str, settings: Settings, request_id: str = "") -> LinkRead:
    creation_enabled(settings)
    destination = validate_destination(value, settings)
    try:
        for _ in range(MAX_CREATION_ATTEMPTS):
            code = generate_code()
            if not usable_code(code):
                continue
            link = insert_candidate(session, destination, code)
            if link is None:
                continue
            session.commit()
            logging.getLogger("minify.links").info("link_created request_id=%s", request_id)
            return LinkRead(
                id=link.id,
                original_url=link.original_url,
                short_code=link.short_code,
                short_url=f"{str(settings.base_url).rstrip('/')}/{link.short_code}",
                is_active=link.is_active,
                created_at=link.created_at,
            )
        raise AppError(
            503,
            "SHORT_CODE_GENERATION_EXHAUSTED",
            "Unable to allocate a short link. Try again later.",
        )
    except Exception as error:
        session.rollback()
        if database_unavailable(error):
            log_failure(f"link_creation_unavailable request_id={request_id}", error)
            raise AppError(
                503, "DATABASE_UNAVAILABLE", "The link service is temporarily unavailable."
            ) from None
        raise


def resolve_link(session: Session, code: str, settings: Settings, request_id: str = "") -> str:
    missing = AppError(404, "LINK_NOT_FOUND", "This short link was not found or is inactive.")
    if not usable_code(code):
        raise missing
    try:
        link = find_link(session, code)
        if link is None or not link.is_active:
            raise missing
        try:
            destination = validate_destination(link.original_url, settings)
        except AppError:
            logging.getLogger("minify.links").warning(
                "unsafe_stored_link request_id=%s", request_id
            )
            raise missing from None
        return destination
    except Exception as error:
        session.rollback()
        if database_unavailable(error):
            log_failure(f"link_resolution_unavailable request_id={request_id}", error)
            raise AppError(
                503, "DATABASE_UNAVAILABLE", "The link service is temporarily unavailable."
            ) from None
        raise
