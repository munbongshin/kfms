"""Accuracy evaluation: eval_cases, eval_runs

Revision ID: 009
Revises: 008
Create Date: 2026-09-30 19:00:00.000000

Idempotent like 002-008: a fresh volume gets both tables from
docker/init/01_schema.sql.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if not _has('eval_cases'):
        op.create_table(
            'eval_cases',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('question', sa.Text(), nullable=False),
            sa.Column('expected_sql', sa.Text(), nullable=False),
            sa.Column('database_id', sa.String(length=255), nullable=False),
            sa.Column('created_by', sa.String(length=60), nullable=False, server_default=''),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
        )
    if not _has('eval_runs'):
        op.create_table(
            'eval_runs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('database_id', sa.String(length=255), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='running'),
            sa.Column('provider', sa.String(length=60), nullable=False, server_default=''),
            sa.Column('model', sa.String(length=200), nullable=False, server_default=''),
            sa.Column('total', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('passed', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('seconds', sa.Float(), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('started_by', sa.String(length=60), nullable=False, server_default=''),
            sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    for table in ('eval_runs', 'eval_cases'):
        if _has(table):
            op.drop_table(table)
