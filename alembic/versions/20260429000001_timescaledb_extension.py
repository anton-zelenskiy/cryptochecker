"""install timescaledb extension

Revision ID: 20260429000001
Revises:
Create Date: 2026-04-29 00:00:01.000000
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text


revision = '20260429000001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text('CREATE EXTENSION IF NOT EXISTS timescaledb;'))


def downgrade() -> None:
    op.execute(text('DROP EXTENSION IF EXISTS timescaledb;'))
