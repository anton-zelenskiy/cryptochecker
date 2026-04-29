"""catalog: add source column + composite identity

Revision ID: 20260429194000
Revises: 20260429100000
Create Date: 2026-04-29 19:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429194000"
down_revision = "20260429100000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "catalog_coins",
        sa.Column("source", sa.String(length=32), server_default="coingecko", nullable=False),
    )
    op.create_index("ix_catalog_source", "catalog_coins", ["source"], unique=False)
    op.drop_constraint("uq_catalog_coingecko_id", "catalog_coins", type_="unique")
    op.create_unique_constraint("uq_catalog_coin_identity", "catalog_coins", ["source", "coingecko_id"])


def downgrade() -> None:
    op.drop_constraint("uq_catalog_coin_identity", "catalog_coins", type_="unique")
    op.create_unique_constraint("uq_catalog_coingecko_id", "catalog_coins", ["coingecko_id"])
    op.drop_index("ix_catalog_source", table_name="catalog_coins")
    op.drop_column("catalog_coins", "source")

