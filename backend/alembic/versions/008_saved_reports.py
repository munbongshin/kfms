"""Scheduled reports: saved_reports

Revision ID: 008
Revises: 007
Create Date: 2026-09-30 17:00:00.000000

Idempotent like 002-007: a fresh volume gets the table from
docker/init/01_schema.sql.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'saved_reports'


def _has_table() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def upgrade() -> None:
    if not _has_table():
        op.create_table(
            TABLE,
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('question', sa.Text(), nullable=False, server_default=''),
            sa.Column('sql', sa.Text(), nullable=False),
            sa.Column('database_id', sa.String(length=255), nullable=False),
            sa.Column('frequency', sa.String(length=20), nullable=False, server_default='daily'),
            sa.Column('run_hour', sa.Integer(), nullable=False, server_default='9'),
            sa.Column('run_weekday', sa.Integer(), nullable=True),
            sa.Column('run_day', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('next_run_at', sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column('last_run_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('last_status', sa.String(length=20), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('last_row_count', sa.Integer(), nullable=True),
            sa.Column('last_results', sa.JSON(), nullable=True),
            sa.Column('created_by', sa.String(length=60), nullable=False, server_default=''),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('idx_saved_reports_due', TABLE, ['next_run_at'])


def downgrade() -> None:
    if _has_table():
        op.drop_table(TABLE)
