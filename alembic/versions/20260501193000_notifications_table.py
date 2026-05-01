"""notifications table (dedup sent screener signals)

Revision ID: 20260501193000
Revises: 20260502100000
Create Date: 2026-05-01 19:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260501193000"
down_revision = "20260502100000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("base_asset", sa.String(length=16), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("decision", sa.String(length=8), nullable=False),
        sa.Column("bucket_date_utc", sa.Date(), nullable=False),
        sa.Column("asof_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "decision",
            "bucket_date_utc",
            "channel",
            name="uq_notification_dedup",
        ),
    )
    op.create_index(
        "ix_notifications_market_time",
        "notifications",
        ["base_asset", "quote_asset", "asof_time_utc"],
        unique=False,
    )
    op.create_index("ix_notifications_bucket", "notifications", ["bucket_date_utc"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_bucket", table_name="notifications")
    op.drop_index("ix_notifications_market_time", table_name="notifications")
    op.drop_table("notifications")

