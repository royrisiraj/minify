from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Link


def insert_candidate(session: Session, destination: str, code: str) -> Link | None:
    # Only this named constraint is recoverable; other integrity failures must propagate.
    statement = (
        insert(Link)
        .values(id=uuid4(), original_url=destination, short_code=code)
        .on_conflict_do_nothing(constraint="uq_links_short_code")
        .returning(Link)
    )
    return session.execute(statement).scalar_one_or_none()


def find_link(session: Session, code: str) -> Link | None:
    return session.scalar(select(Link).where(Link.short_code == code))
