"""coin metadata table (platforms/contracts)

Revision ID: 20260429194500
Revises: 20260429194000
Create Date: 2026-04-29 19:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429194500"
down_revision = "20260429194000"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_coin_metadata_fetched_at", table_name="coin_metadata")
    op.drop_index("ix_coin_metadata_coin", table_name="coin_metadata")
    op.drop_table("coin_metadata")

