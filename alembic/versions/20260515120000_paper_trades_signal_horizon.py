"""paper_trades: signal_horizon from screener bias stack

Revision ID: 20260515120000
Revises: 20260502180000
Create Date: 2026-05-15

"""

from alembic import op
import sqlalchemy as sa


revision = "20260515120000"
down_revision = "20260502180000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paper_trades",
        sa.Column("signal_horizon", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("paper_trades", "signal_horizon")
