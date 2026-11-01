"""resume_filename on reports

Revision ID: b5d6e7f8a9c0
Revises: a3c4d5e6f7b8
Create Date: 2026-11-01 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5d6e7f8a9c0"
down_revision: str | Sequence[str] | None = "a3c4d5e6f7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: reports created before this have no file name to backfill.
    with op.batch_alter_table("reports") as batch:
        batch.add_column(sa.Column("resume_filename", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.drop_column("resume_filename")
