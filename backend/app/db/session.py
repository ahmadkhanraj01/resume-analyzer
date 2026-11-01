"""Engine and session factory. Knows nothing about HTTP."""

import logging
from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def make_engine(settings: Settings):
    if settings.database_url.startswith("sqlite"):
        return create_engine(
            settings.database_url, echo=False, connect_args={"check_same_thread": False}
        )
    # Neon suspends an idle compute after 5 minutes and Render sleeps the API
    # after 15, so a pooled connection may be dead when it is next used:
    # pre_ping replaces it instead of failing the request.
    return create_engine(settings.database_url, echo=False, pool_pre_ping=True)


engine = make_engine(get_settings())


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def _sql_literal(value) -> str:
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if hasattr(value, "text"):  # text("...") server defaults are raw SQL
        return value.text
    return str(value)


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
                # String defaults must be SQL-quoted: a bare DEFAULT [] is an
                # empty identifier to SQLite and backfills old rows with ''.
                if column.server_default is not None:
                    ddl += f" DEFAULT {_sql_literal(column.server_default.arg)}"
                elif column.default is not None and column.default.is_scalar:
                    ddl += f" DEFAULT {_sql_literal(column.default.arg)}"
                conn.execute(text(ddl))
                logger.info("sqlite dev schema: added %s.%s", table.name, column.name)
