"""Business glossary: glossary_terms

Revision ID: 005
Revises: 004
Create Date: 2026-09-30 10:00:00.000000

Idempotent like 002-004: a fresh volume gets the table from
docker/init/01_schema.sql.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'glossary_terms'


def _has_table() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def upgrade() -> None:
    if not _has_table():
        op.create_table(
            TABLE,
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('term', sa.String(length=100), nullable=False),
            sa.Column('definition', sa.Text(), nullable=False),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('term'),
        )


def downgrade() -> None:
    if _has_table():
        op.drop_table(TABLE)
