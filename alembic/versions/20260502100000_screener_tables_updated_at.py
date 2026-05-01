"""align screener tables with CustomBase timestamps (updated_at / created_at)

Revision ID: 20260502100000
Revises: 20260501120000
Create Date: 2026-05-02 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260502100000"
down_revision = "20260501120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "fvg_zones",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        server_default=sa.text("now()"),
    )
    op.add_column(
        "fvg_zones",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.add_column(
        "screener_snapshots",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "screener_snapshots",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.add_column(
        "fundamentals_snapshots",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "fundamentals_snapshots",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("fundamentals_snapshots", "updated_at")
    op.drop_column("fundamentals_snapshots", "created_at")
    op.drop_column("screener_snapshots", "updated_at")
    op.drop_column("screener_snapshots", "created_at")
    op.drop_column("fvg_zones", "updated_at")
    op.alter_column(
        "fvg_zones",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        server_default=None,
    )
