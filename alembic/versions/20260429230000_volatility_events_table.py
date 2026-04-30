"""volatility events table (big moves)

Revision ID: 20260429230000
Revises: 20260429195500
Create Date: 2026-04-29 23:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429230000"
down_revision = "20260429195500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "volatility_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("base_asset", sa.String(length=16), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("bucket_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pct_change", sa.Float(), nullable=False),
        sa.Column("range_pct", sa.Float(), nullable=False),
        sa.Column("volume_quote", sa.Float(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "timeframe",
            "event_type",
            "bucket_time_utc",
            name="uq_volatility_event_dedup",
        ),
    )
    op.create_index(
        "ix_volatility_events_market_time",
        "volatility_events",
        ["base_asset", "quote_asset", "timeframe", "bucket_time_utc"],
        unique=False,
    )
    op.create_index(
        "ix_volatility_events_detected_at",
        "volatility_events",
        ["detected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_volatility_events_detected_at", table_name="volatility_events")
    op.drop_index("ix_volatility_events_market_time", table_name="volatility_events")
    op.drop_table("volatility_events")

