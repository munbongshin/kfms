"""Anomaly detection: anomaly_review

Revision ID: 002
Revises: 001
Create Date: 2026-09-22 10:00:00.000000

Task 4 applied this DDL to the running kfms database by hand, and
docker/init/01_schema.sql creates it on a *fresh* volume only. Neither path
covers an existing deployment, where the feature would fail with UndefinedTable.
This revision closes that gap.

It is deliberately idempotent: the init script and this migration must not fight
each other, so on a container whose volume already ran 01_schema.sql the upgrade
is a no-op rather than a DuplicateTable error.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'anomaly_review'
INDEX = 'idx_anomaly_review_lookup'


def _has_table() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def _has_index() -> bool:
    return INDEX in {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(TABLE)}


def upgrade() -> None:
    if not _has_table():
        op.create_table(
            TABLE,
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('database_id', sa.String(length=255), nullable=False, comment='Database connection ID the finding belongs to'),
            sa.Column('finding_key', sa.String(length=200), nullable=False, comment='RULE_CODE:subject identity of the finding'),
            sa.Column('rule_code', sa.String(length=40), nullable=False, comment='Rule that produced the finding'),
            sa.Column('status', sa.String(length=20), nullable=False, comment='confirmed or dismissed'),
            sa.Column('fingerprint', sa.String(length=64), nullable=False, comment='Finding content when reviewed; a mismatch reopens it'),
            sa.Column('note', sa.Text(), nullable=True, comment="Reviewer's free-text note"),
            sa.Column('reviewed_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='When the decision was recorded'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('database_id', 'finding_key'),
        )

    if not _has_index():
        op.create_index(INDEX, TABLE, ['database_id', 'rule_code'], unique=False)


def downgrade() -> None:
    if _has_table():
        if _has_index():
            op.drop_index(INDEX, table_name=TABLE)
        op.drop_table(TABLE)
