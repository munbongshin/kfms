"""History of anomaly-setting changes: anomaly_setting_history

Revision ID: 012
Revises: 011
Create Date: 2026-09-30 22:00:00.000000

Each change to the thresholds keeps who, when, the values before and after (so an
earlier state can be restored) and the readable list of what moved. Idempotent
like 002-011: a fresh volume gets the table from docker/init/01_schema.sql.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'anomaly_setting_history'


def _has_table() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def upgrade() -> None:
    if not _has_table():
        op.create_table(
            TABLE,
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('changed_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('changed_by', sa.String(length=60), nullable=False, server_default=''),
            sa.Column('before', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column('after', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column('changes', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    if _has_table():
        op.drop_table(TABLE)
