"""screener v2: snapshots, fvg zones, fundamentals, indicator columns

Revision ID: 20260501120000
Revises: 20260430203000
Create Date: 2026-05-01 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260501120000"
down_revision = "20260430203000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screener_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("base_asset", sa.String(length=16), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("asof_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature_version", sa.String(length=8), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(length=8), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("long_score", sa.Float(), nullable=False),
        sa.Column("short_score", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("llm_verdict", sa.String(length=24), nullable=True),
        sa.Column("llm_confidence_adjust", sa.Float(), nullable=True),
        sa.Column("llm_rationale", sa.String(length=2048), nullable=True),
        sa.Column("final_decision", sa.String(length=8), nullable=False),
        sa.Column("final_confidence", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "asof_time_utc",
            name="uq_screener_snapshot_identity",
        ),
    )
    op.create_index(
        "ix_screener_snapshots_market_time",
        "screener_snapshots",
        ["base_asset", "quote_asset", "computed_at"],
        unique=False,
    )

    op.create_table(
        "fvg_zones",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("base_asset", sa.String(length=16), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("zone_low", sa.Float(), nullable=False),
        sa.Column("zone_high", sa.Float(), nullable=False),
        sa.Column("formed_at_open_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mitigated_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "base_asset",
            "quote_asset",
            "timeframe",
            "formed_at_open_time_utc",
            "direction",
            name="uq_fvg_zone_identity",
        ),
    )
    op.create_index(
        "ix_fvg_zones_market_tf",
        "fvg_zones",
        ["base_asset", "quote_asset", "timeframe", "formed_at_open_time_utc"],
        unique=False,
    )

    op.create_table(
        "fundamentals_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("coingecko_id", sa.String(length=128), nullable=False),
        sa.Column("base_symbol", sa.String(length=32), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market_cap_usd", sa.Float(), nullable=True),
        sa.Column("fdv_usd", sa.Float(), nullable=True),
        sa.Column("total_volume_24h_usd", sa.Float(), nullable=True),
        sa.Column("tvl_usd", sa.Float(), nullable=True),
        sa.Column("mcap_to_tvl", sa.Float(), nullable=True),
        sa.Column("fdv_to_tvl", sa.Float(), nullable=True),
        sa.Column("flag_overpriced", sa.Boolean(), nullable=False),
        sa.Column("flag_undervalued_tvl", sa.Boolean(), nullable=False),
        sa.Column("tvl_unavailable", sa.Boolean(), nullable=False),
        sa.Column("raw_extras", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fundamentals_coingecko_time",
        "fundamentals_snapshots",
        ["coingecko_id", "fetched_at"],
        unique=False,
    )
    op.create_index(
        "ix_fundamentals_symbol_time",
        "fundamentals_snapshots",
        ["base_symbol", "fetched_at"],
        unique=False,
    )

    op.add_column("indicator_snapshots", sa.Column("ema_20", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("ema_50", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("ema_200", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("macd", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("macd_signal", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("macd_hist", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("atr_14", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("adx_14", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("bb_upper", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("bb_mid", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("bb_lower", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("mfi_14", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("obv", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("stochrsi_k", sa.Float(), nullable=True))
    op.add_column("indicator_snapshots", sa.Column("stochrsi_d", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("indicator_snapshots", "stochrsi_d")
    op.drop_column("indicator_snapshots", "stochrsi_k")
    op.drop_column("indicator_snapshots", "obv")
    op.drop_column("indicator_snapshots", "mfi_14")
    op.drop_column("indicator_snapshots", "bb_lower")
    op.drop_column("indicator_snapshots", "bb_mid")
    op.drop_column("indicator_snapshots", "bb_upper")
    op.drop_column("indicator_snapshots", "adx_14")
    op.drop_column("indicator_snapshots", "atr_14")
    op.drop_column("indicator_snapshots", "macd_hist")
    op.drop_column("indicator_snapshots", "macd_signal")
    op.drop_column("indicator_snapshots", "macd")
    op.drop_column("indicator_snapshots", "ema_200")
    op.drop_column("indicator_snapshots", "ema_50")
    op.drop_column("indicator_snapshots", "ema_20")

    op.drop_index("ix_fundamentals_symbol_time", table_name="fundamentals_snapshots")
    op.drop_index("ix_fundamentals_coingecko_time", table_name="fundamentals_snapshots")
    op.drop_table("fundamentals_snapshots")

    op.drop_index("ix_fvg_zones_market_tf", table_name="fvg_zones")
    op.drop_table("fvg_zones")

    op.drop_index("ix_screener_snapshots_market_time", table_name="screener_snapshots")
    op.drop_table("screener_snapshots")
