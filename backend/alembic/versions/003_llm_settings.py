"""LLM settings: llm_settings

Revision ID: 003
Revises: 002
Create Date: 2026-09-28 10:00:00.000000

Stores the LLM serving platform chosen on the settings screen, with each
platform's address, model and (encrypted) key in `profiles`. Idempotent for the
same reason as 002: docker/init/01_schema.sql creates the table on a fresh
volume, and this revision must be a no-op there rather than a DuplicateTable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'llm_settings'


def _has_table() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def upgrade() -> None:
    if not _has_table():
        op.create_table(
            TABLE,
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('provider', sa.String(length=40), nullable=True, comment='Chosen platform'),
            sa.Column('profiles', sa.JSON(), nullable=False, server_default=sa.text("'{}'"), comment='Per-platform settings; api_key encrypted'),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    if _has_table():
        op.drop_table(TABLE)
