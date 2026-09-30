"""Announced holidays: synced_holidays, holiday_sync

Revision ID: 013
Revises: 012
Create Date: 2026-09-30 23:00:00.000000

synced_holidays holds the days received by the holiday sync (an announced
임시공휴일 among them); holiday_sync is a single row with the Fernet-encrypted
service key and the outcome of the last sync. Idempotent like 002-012: a fresh
volume gets both tables from docker/init/01_schema.sql.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '013'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table('synced_holidays'):
        op.create_table(
            'synced_holidays',
            sa.Column('day', sa.String(length=10), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False, server_default=''),
            sa.Column('source', sa.String(length=20), nullable=False, server_default=''),
            sa.Column('fetched_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('day'),
        )
    if not _has_table('holiday_sync'):
        op.create_table(
            'holiday_sync',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('service_key', sa.Text(), nullable=True),
            sa.Column('last_synced_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('last_status', sa.String(length=20), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('last_source', sa.String(length=20), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    for name in ('holiday_sync', 'synced_holidays'):
        if _has_table(name):
            op.drop_table(name)
