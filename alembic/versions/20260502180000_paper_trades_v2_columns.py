"""paper_trades v2: SL/TP, snapshot link, exit_reason

Revision ID: 20260502180000
Revises: 20260502120000
Create Date: 2026-05-02 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260502180000"
down_revision = "20260502120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "paper_trades",
        "hold_candles",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column("paper_trades", sa.Column("stop_loss", sa.Float(), nullable=True))
    op.add_column("paper_trades", sa.Column("take_profit", sa.Float(), nullable=True))
    op.add_column("paper_trades", sa.Column("risk_r", sa.Float(), nullable=True))
    op.add_column("paper_trades", sa.Column("atr_used", sa.Float(), nullable=True))
    op.add_column("paper_trades", sa.Column("atr_timeframe", sa.String(length=8), nullable=True))
    op.add_column("paper_trades", sa.Column("tpsl_method", sa.String(length=32), nullable=True))
    op.add_column("paper_trades", sa.Column("confidence_at_entry", sa.Float(), nullable=True))
    op.add_column(
        "paper_trades",
        sa.Column("screener_snapshot_id", sa.Integer(), nullable=True),
    )
    op.add_column("paper_trades", sa.Column("exit_reason", sa.String(length=16), nullable=True))
    op.create_foreign_key(
        "fk_paper_trades_screener_snapshot_id",
        "paper_trades",
        "screener_snapshots",
        ["screener_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_paper_trades_screener_snapshot_id", "paper_trades", type_="foreignkey")
    op.drop_column("paper_trades", "exit_reason")
    op.drop_column("paper_trades", "screener_snapshot_id")
    op.drop_column("paper_trades", "confidence_at_entry")
    op.drop_column("paper_trades", "tpsl_method")
    op.drop_column("paper_trades", "atr_timeframe")
    op.drop_column("paper_trades", "atr_used")
    op.drop_column("paper_trades", "risk_r")
    op.drop_column("paper_trades", "take_profit")
    op.drop_column("paper_trades", "stop_loss")
    op.execute(sa.text("UPDATE paper_trades SET hold_candles = 12 WHERE hold_candles IS NULL"))
    op.alter_column(
        "paper_trades",
        "hold_candles",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="12",
    )
    op.alter_column("paper_trades", "hold_candles", server_default=None)
