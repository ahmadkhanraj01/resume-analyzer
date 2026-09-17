"""scored_against and role_title on reports

Revision ID: 9b2d3e4f5a6c
Revises: 8a1c2f3e4d5b
Create Date: 2026-09-17 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9b2d3e4f5a6c"
down_revision: str | Sequence[str] | None = "8a1c2f3e4d5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.add_column(
            sa.Column(
                "scored_against",
                sa.String(),
                nullable=False,
                server_default="job_description",
            )
        )
        batch.add_column(sa.Column("role_title", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.drop_column("role_title")
        batch.drop_column("scored_against")
