"""candles hypertable, compression, retention

Revision ID: 20260429100000
Revises: 20260429024004
Create Date: 2026-04-29 10:00:00.000000
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text


revision = '20260429100000'
down_revision = '20260429024004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        text(
            """
            SELECT create_hypertable(
                'candles',
                'open_time_utc',
                if_not_exists => TRUE
            );
            """
        )
    )
    op.execute(
        text(
            """
            ALTER TABLE candles SET (
              timescaledb.compress,
              timescaledb.compress_segmentby = 'source,base_asset,quote_asset,timeframe'
            );
            """
        )
    )
    op.execute(
        text(
            """
            SELECT add_compression_policy('candles', INTERVAL '7 days', if_not_exists => TRUE);
            """
        )
    )
    op.execute(
        text(
            """
            SELECT add_retention_policy('candles', INTERVAL '90 days', if_not_exists => TRUE);
            """
        )
    )


def downgrade() -> None:
    op.execute(
        text(
            """
            SELECT remove_retention_policy('candles', if_exists => TRUE);
            """
        )
    )
    op.execute(
        text(
            """
            SELECT remove_compression_policy('candles', if_exists => TRUE);
            """
        )
    )
    op.execute(
        text(
            """
            ALTER TABLE candles RESET (
              timescaledb.compress,
              timescaledb.compress_segmentby
            );
            """
        )
    )
