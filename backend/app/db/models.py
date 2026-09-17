"""SQLModel tables. No validation logic here; that lives in app/schemas/."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# JSONB on Postgres, plain JSON on SQLite (used by tests and local dev).
# Nested report data is always read as a whole document, never queried by an
# inner field, so this is purely a storage type choice, not a query one.
_json_variant = JSONB().with_variant(JSON(), "sqlite")


def _json_column() -> Column:
    # The app always writes a list, so the column is NOT NULL with an empty
    # array default rather than nullable.
    return Column(_json_variant, nullable=False, server_default="[]")


def _timestamp_column(index: bool = False) -> Column:
    # timezone=True is timestamptz on Postgres; without it the UTC offset
    # from datetime.now(UTC) is silently dropped on write.
    return Column(DateTime(timezone=True), nullable=False, index=index)


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=_uuid_str, primary_key=True)
    email: str = Field(unique=True, index=True, nullable=False)
    password_hash: str
    created_at: datetime = Field(default_factory=_now, sa_column=_timestamp_column())


class Report(SQLModel, table=True):
    __tablename__ = "reports"

    id: str = Field(default_factory=_uuid_str, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, nullable=False)
    title: str
    job_description: str
    self_description: str = ""
    resume_text: str
    match_score: int
    skill_gaps: list = Field(default_factory=list, sa_column=_json_column())
    technical_qs: list = Field(default_factory=list, sa_column=_json_column())
    behavioral_qs: list = Field(default_factory=list, sa_column=_json_column())
    preparation_plan: list = Field(default_factory=list, sa_column=_json_column())
    created_at: datetime = Field(default_factory=_now, sa_column=_timestamp_column(index=True))
