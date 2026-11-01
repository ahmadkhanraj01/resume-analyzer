"""resume_keywords and resume_rewrites on reports

Revision ID: a3c4d5e6f7b8
Revises: 9b2d3e4f5a6c
Create Date: 2026-11-01 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a3c4d5e6f7b8"
down_revision: str | Sequence[str] | None = "9b2d3e4f5a6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_json = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    # server_default "[]" fills existing rows, so reports made before this
    # migration read back with empty suggestions instead of NULL.
    with op.batch_alter_table("reports") as batch:
        batch.add_column(sa.Column("resume_keywords", _json, nullable=False, server_default="[]"))
        batch.add_column(sa.Column("resume_rewrites", _json, nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.drop_column("resume_rewrites")
        batch.drop_column("resume_keywords")
