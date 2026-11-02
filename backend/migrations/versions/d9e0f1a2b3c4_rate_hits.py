"""rate_hits table for database-backed rate limits

Revision ID: d9e0f1a2b3c4
Revises: c7e8f9a0b1d2
Create Date: 2026-11-02 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: str | Sequence[str] | None = "c7e8f9a0b1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_hits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bucket", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_hits_bucket", "rate_hits", ["bucket"])
    op.create_index("ix_rate_hits_created_at", "rate_hits", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_rate_hits_created_at", table_name="rate_hits")
    op.drop_index("ix_rate_hits_bucket", table_name="rate_hits")
    op.drop_table("rate_hits")
