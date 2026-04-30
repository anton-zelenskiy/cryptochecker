"""orderbook walls + trade clusters tables

Revision ID: 20260430203000
Revises: 20260429230000
Create Date: 2026-04-30 20:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260430203000"
down_revision = "20260429230000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orderbook_walls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("base_asset", sa.String(length=16), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("bucket_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wall_price", sa.Float(), nullable=False),
        sa.Column("wall_qty", sa.Float(), nullable=False),
        sa.Column("wall_notional_quote", sa.Float(), nullable=False),
        sa.Column("best_bid", sa.Float(), nullable=True),
        sa.Column("median_bid_qty", sa.Float(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "bucket_time_utc",
            "wall_price",
            name="uq_orderbook_wall_identity",
        ),
    )
    op.create_index(
        "ix_orderbook_walls_market_time",
        "orderbook_walls",
        ["base_asset", "quote_asset", "bucket_time_utc"],
        unique=False,
    )
    op.create_index(
        "ix_orderbook_walls_detected_at",
        "orderbook_walls",
        ["detected_at"],
        unique=False,
    )

    op.create_table(
        "trade_clusters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("base_asset", sa.String(length=16), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("window_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("buy_notional_quote", sa.Float(), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "window_start_utc",
            "window_seconds",
            name="uq_trade_cluster_identity",
        ),
    )
    op.create_index(
        "ix_trade_clusters_market_time",
        "trade_clusters",
        ["base_asset", "quote_asset", "window_start_utc"],
        unique=False,
    )
    op.create_index(
        "ix_trade_clusters_detected_at",
        "trade_clusters",
        ["detected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_trade_clusters_detected_at", table_name="trade_clusters")
    op.drop_index("ix_trade_clusters_market_time", table_name="trade_clusters")
    op.drop_table("trade_clusters")

    op.drop_index("ix_orderbook_walls_detected_at", table_name="orderbook_walls")
    op.drop_index("ix_orderbook_walls_market_time", table_name="orderbook_walls")
    op.drop_table("orderbook_walls")
