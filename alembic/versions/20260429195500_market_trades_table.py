"""market trades table (ws prints, trades-only slice)

Revision ID: 20260429195500
Revises: 20260429194500
Create Date: 2026-04-29 19:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429195500"
down_revision = "20260429194500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("base_asset", sa.String(length=16), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("trade_id", sa.String(length=128), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("notional_quote", sa.Float(), nullable=False),
        sa.Column("trade_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "trade_id", name="uq_market_trades_identity"),
    )
    op.create_index(
        "ix_market_trades_market_time",
        "market_trades",
        ["base_asset", "quote_asset", "trade_time_utc"],
        unique=False,
    )
    op.create_index(
        "ix_market_trades_source_time",
        "market_trades",
        ["source", "trade_time_utc"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_trades_source_time", table_name="market_trades")
    op.drop_index("ix_market_trades_market_time", table_name="market_trades")
    op.drop_table("market_trades")

