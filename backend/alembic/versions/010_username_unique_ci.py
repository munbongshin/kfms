"""Usernames are unique without regard to case

Revision ID: 010
Revises: 009
Create Date: 2026-09-30 20:00:00.000000

The application already refuses a duplicate id, but two requests arriving
together could both pass that check. A unique index on lower(username) makes the
database refuse the second one. Idempotent like 002-009.

If existing users differ only by case this cannot be created; rename one first.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX = 'ux_app_users_username_lower'


def upgrade() -> None:
    op.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {INDEX} ON app_users (lower(username))")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX}")
