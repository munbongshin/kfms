"""Users and the audit log: app_users, audit_log

Revision ID: 006
Revises: 005
Create Date: 2026-09-30 12:00:00.000000

Idempotent like 002-005: a fresh volume gets both tables from
docker/init/01_schema.sql.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if not _has('app_users'):
        op.create_table(
            'app_users',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('username', sa.String(length=60), nullable=False),
            sa.Column('display_name', sa.String(length=100), nullable=False, server_default=''),
            sa.Column('password_hash', sa.String(length=300), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False, server_default='viewer'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('last_login_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('username'),
        )
    if not _has('audit_log'):
        op.create_table(
            'audit_log',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('username', sa.String(length=60), nullable=False, server_default=''),
            sa.Column('role', sa.String(length=20), nullable=False, server_default=''),
            sa.Column('action', sa.String(length=60), nullable=False),
            sa.Column('target', sa.String(length=500), nullable=False, server_default=''),
            sa.Column('detail', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column('ip', sa.String(length=64), nullable=False, server_default=''),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('idx_audit_log_at', 'audit_log', ['at'])


def downgrade() -> None:
    if _has('audit_log'):
        op.drop_table('audit_log')
    if _has('app_users'):
        op.drop_table('app_users')
