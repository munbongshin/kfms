"""Anomaly thresholds: anomaly_settings

Revision ID: 007
Revises: 006
Create Date: 2026-09-30 15:00:00.000000

Idempotent like 002-006: a fresh volume gets the table from
docker/init/01_schema.sql.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'anomaly_settings'


def _has_table() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def upgrade() -> None:
    if not _has_table():
        op.create_table(
            TABLE,
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('params', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    if _has_table():
        op.drop_table(TABLE)
