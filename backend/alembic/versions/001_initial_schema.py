"""Initial schema: query_history, database_connections, excel_uploads

Revision ID: 001
Revises:
Create Date: 2026-09-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create query_history table
    op.create_table(
        'query_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('question', sa.Text(), nullable=False, comment="User's natural language question"),
        sa.Column('generated_sql', sa.Text(), nullable=False, comment='LLM-generated SQL query'),
        sa.Column('database_id', sa.String(length=255), nullable=False, comment='Database connection ID used'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending', comment='Query execution status: pending, success, error'),
        sa.Column('results', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='Query results (first 1000 rows)'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error details if execution failed'),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True, comment='Query execution time in milliseconds'),
        sa.Column('row_count', sa.Integer(), nullable=True, comment='Total number of rows returned'),
        sa.Column('llm_provider', sa.String(length=50), nullable=True, comment='LLM provider used: ollama or groq'),
        sa.Column('llm_model', sa.String(length=100), nullable=True, comment='Specific model name'),
        sa.Column('validation_approved', sa.Boolean(), nullable=False, server_default='false', comment='User confirmed execution after seeing SQL'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Timestamp when query was created'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_query_history_created_at', 'query_history', ['created_at'], unique=False, postgresql_ops={'created_at': 'DESC'})
    op.create_index('idx_query_history_database_id', 'query_history', ['database_id'], unique=False)
    op.create_index('idx_query_history_status', 'query_history', ['status'], unique=False)

    # Create database_connections table
    op.create_table(
        'database_connections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, comment='User-friendly connection name'),
        sa.Column('host', sa.String(length=255), nullable=False, comment='Database host address'),
        sa.Column('port', sa.Integer(), nullable=False, server_default='5432', comment='Database port'),
        sa.Column('database', sa.String(length=255), nullable=False, comment='Database name'),
        sa.Column('username', sa.String(length=255), nullable=False, comment='Database username'),
        sa.Column('password', sa.String(length=255), nullable=False, comment='Encrypted password (Fernet)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', comment='Connection enabled status'),
        sa.Column('is_read_only', sa.Boolean(), nullable=False, server_default='true', comment='Enforce read-only mode (SELECT only)'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Connection creation timestamp'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Last update timestamp'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_database_connections_name', 'database_connections', ['name'], unique=False)

    # Create excel_uploads table
    op.create_table(
        'excel_uploads',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False, comment='Original Excel filename'),
        sa.Column('table_name', sa.String(length=255), nullable=False, comment='Generated temporary table name in database'),
        sa.Column('row_count', sa.Integer(), nullable=True, comment='Number of rows in Excel file'),
        sa.Column('column_count', sa.Integer(), nullable=True, comment='Number of columns in Excel file'),
        sa.Column('schema_info', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='Column names and inferred data types'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Upload timestamp'),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='Expiration timestamp for automatic cleanup'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('table_name')
    )
    op.create_index('idx_excel_uploads_expires_at', 'excel_uploads', ['expires_at'], unique=False)
    op.create_index('idx_excel_uploads_table_name', 'excel_uploads', ['table_name'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_excel_uploads_table_name', table_name='excel_uploads')
    op.drop_index('idx_excel_uploads_expires_at', table_name='excel_uploads')
    op.drop_table('excel_uploads')

    op.drop_index('idx_database_connections_name', table_name='database_connections')
    op.drop_table('database_connections')

    op.drop_index('idx_query_history_status', table_name='query_history')
    op.drop_index('idx_query_history_database_id', table_name='query_history')
    op.drop_index('idx_query_history_created_at', table_name='query_history')
    op.drop_table('query_history')
