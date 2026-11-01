"""skill_lists table for stable LLM-named skill lists

Revision ID: c7e8f9a0b1d2
Revises: b5d6e7f8a9c0
Create Date: 2026-11-01 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c7e8f9a0b1d2"
down_revision: str | Sequence[str] | None = "b5d6e7f8a9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_lists",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column(
            "skills",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("skill_lists")
