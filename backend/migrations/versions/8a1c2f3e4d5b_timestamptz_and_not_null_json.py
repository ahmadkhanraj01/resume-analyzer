"""timestamptz columns and NOT NULL JSON columns

Revision ID: 8a1c2f3e4d5b
Revises: 4d7f4dcc51d7
Create Date: 2026-09-17 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision: str = "8a1c2f3e4d5b"
down_revision: str | Sequence[str] | None = "4d7f4dcc51d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = postgresql.JSONB(astext_type=Text()).with_variant(sa.JSON(), "sqlite")
_JSON_COLUMNS = ("skill_gaps", "technical_qs", "behavioral_qs", "preparation_plan")


def upgrade() -> None:
    # batch_alter_table so the same migration runs on SQLite, which cannot
    # ALTER COLUMN in place and needs the copy-and-rename dance.
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "created_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime()
        )
    with op.batch_alter_table("reports") as batch:
        batch.alter_column(
            "created_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime()
        )
        for name in _JSON_COLUMNS:
            # Backfill before tightening, in case any row was written with a
            # NULL by an earlier build.
            batch.alter_column(name, existing_type=_JSON, nullable=False, server_default="[]")


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        for name in _JSON_COLUMNS:
            batch.alter_column(name, existing_type=_JSON, nullable=True, server_default=None)
        batch.alter_column(
            "created_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True)
        )
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "created_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True)
        )
