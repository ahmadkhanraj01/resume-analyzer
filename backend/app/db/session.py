"""Engine and session factory. Knows nothing about HTTP."""

import logging
from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def make_engine(settings: Settings):
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(settings.database_url, echo=False, connect_args=connect_args)


engine = make_engine(get_settings())


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def sync_sqlite_schema(engine) -> None:
    """Dev-only stand-in for migrations on SQLite. create_all makes missing
    tables but never touches an existing one, so a dev.db created before a
    model gained a column would 500 on every insert. Postgres is managed by
    Alembic and never goes through here."""
    SQLModel.metadata.create_all(engine)
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} "
                ddl += column.type.compile(dialect=engine.dialect)
                if column.server_default is not None:
                    ddl += f" DEFAULT {column.server_default.arg}"
                elif column.default is not None and column.default.is_scalar:
                    value = column.default.arg
                    ddl += f" DEFAULT {value!r}" if isinstance(value, str) else f" DEFAULT {value}"
                conn.execute(text(ddl))
                logger.info("sqlite dev schema: added %s.%s", table.name, column.name)
