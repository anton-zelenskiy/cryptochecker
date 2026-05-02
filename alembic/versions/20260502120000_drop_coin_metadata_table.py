"""drop coin_metadata table (feature removed)

Revision ID: 20260502120000
Revises: 20260501193000
Create Date: 2026-05-02 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260502120000"
down_revision = "20260501193000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS coin_metadata CASCADE")


def downgrade() -> None:
    op.create_table(
        "coin_metadata",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("coin_id", sa.String(length=128), nullable=False),
        sa.Column("platforms", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "coin_id", name="uq_coin_metadata_identity"),
    )
    op.create_index("ix_coin_metadata_coin", "coin_metadata", ["source", "coin_id"], unique=False)
    op.create_index("ix_coin_metadata_fetched_at", "coin_metadata", ["fetched_at"], unique=False)
