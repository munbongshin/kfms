"""Analysis targets: database_connections.excluded_tables

Revision ID: 004
Revises: 003
Create Date: 2026-09-29 10:00:00.000000

Tables a connection leaves out of text-to-SQL. Idempotent like 002/003: a fresh
volume gets the column from docker/init/01_schema.sql.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'database_connections'
COLUMN = 'excluded_tables'


def _has_column() -> bool:
    return COLUMN in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    if not _has_column():
        op.add_column(
            TABLE,
            sa.Column(COLUMN, sa.JSON(), nullable=False, server_default=sa.text("'[]'"),
                      comment='Tables excluded from text-to-SQL analysis'),
        )


def downgrade() -> None:
    if _has_column():
        op.drop_column(TABLE, COLUMN)
