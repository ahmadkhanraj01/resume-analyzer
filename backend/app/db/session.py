"""Engine and session factory. Knows nothing about HTTP."""

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import Settings, get_settings


def make_engine(settings: Settings):
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(settings.database_url, echo=False, connect_args=connect_args)


engine = make_engine(get_settings())


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
