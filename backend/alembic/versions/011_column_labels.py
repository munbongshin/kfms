"""Column display names an administrator manages: column_labels, expression_terms

Revision ID: 011
Revises: 010
Create Date: 2026-09-30 21:00:00.000000

Replaces the display names that were written in code. The three that were
(appramt, apprtot, curracqutot) are copied to every existing connection so
nothing on screen changes; from here they are ordinary rows an administrator can
edit or delete. Idempotent like 002-010: a fresh volume gets both tables from
docker/init/01_schema.sql.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX = 'ux_column_labels_scope'
# The names that used to be hard-coded in app/db/column_display_names.py.
FORMER_DISPLAY_NAMES = {"appramt": "승인금액", "apprtot": "승인합계", "curracqutot": "매입원금"}


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table('column_labels'):
        op.create_table(
            'column_labels',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('connection_id', sa.Integer(), nullable=False),
            sa.Column('table_key', sa.String(length=255), nullable=True),
            sa.Column('column_name', sa.String(length=128), nullable=False),
            sa.Column('label', sa.String(length=100), nullable=False),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['connection_id'], ['database_connections.id'], ondelete='CASCADE'),
        )
    op.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {INDEX} "
        "ON column_labels (connection_id, (COALESCE(table_key, '')), column_name)"
    )

    if not _has_table('expression_terms'):
        op.create_table(
            'expression_terms',
            sa.Column('func', sa.String(length=20), nullable=False),
            sa.Column('label', sa.String(length=50), nullable=False),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('func'),
        )

    for column, label in FORMER_DISPLAY_NAMES.items():
        op.execute(
            sa.text(
                "INSERT INTO column_labels (connection_id, table_key, column_name, label) "
                "SELECT id, NULL, :column, :label FROM database_connections "
                "ON CONFLICT DO NOTHING"
            ).bindparams(column=column, label=label)
        )


def downgrade() -> None:
    for name in ('expression_terms', 'column_labels'):
        if _has_table(name):
            op.drop_table(name)
