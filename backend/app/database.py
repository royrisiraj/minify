from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, settings: Settings):
        timeout = settings.database_timeout_seconds
        self.engine = create_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_timeout=timeout,
            hide_parameters=True,
            connect_args={
                "connect_timeout": timeout,
                "options": f"-c statement_timeout={timeout * 1000}",
            },
        )
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def check_connection(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def dispose(self) -> None:
        self.engine.dispose()


def get_session(request: Request) -> Generator[Session]:
    """Services explicitly commit successful writes. Exceptions roll back; always close."""
    with request.app.state.database.sessions() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
