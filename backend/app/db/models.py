"""
SQLAlchemy models for KFMS application.
Defines database schema for query history, database connections, and Excel uploads.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, TIMESTAMP, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class QueryHistory(Base):
    """
    Stores execution history of natural language queries.
    Tracks questions, generated SQL, results, and metadata.
    """
    __tablename__ = "query_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False, comment="User's natural language question")
    generated_sql: Mapped[str] = mapped_column(Text, nullable=False, comment="LLM-generated SQL query")
    database_id: Mapped[str] = mapped_column(String(255), nullable=False, comment="Database connection ID used")
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="Query execution status: pending, success, error"
    )
    results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="Query results (first 1000 rows)")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Error details if execution failed")
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Query execution time in milliseconds")
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Total number of rows returned")
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="LLM provider used: ollama or groq")
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Specific model name")
    validation_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="User confirmed execution after seeing SQL"
    )
    is_bookmarked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Saved by the user for one-click re-execution"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when query was created"
    )

    def __repr__(self):
        return f"<QueryHistory(id={self.id}, database={self.database_id}, status={self.status})>"


class DatabaseConnection(Base):
    """
    Stores PostgreSQL database connection configurations.
    Supports multiple databases with encrypted credentials.
    """
    __tablename__ = "database_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, comment="User-friendly connection name")
    host: Mapped[str] = mapped_column(String(255), nullable=False, comment="Database host address")
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=5432, comment="Database port")
    database: Mapped[str] = mapped_column(String(255), nullable=False, comment="Database name")
    username: Mapped[str] = mapped_column(String(255), nullable=False, comment="Database username")
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment="Encrypted password (Fernet)")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="Connection enabled status")
    is_read_only: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enforce read-only mode (SELECT only)"
    )
    # Tables left out of analysis. An exclusion list rather than an inclusion
    # list, so a table that appears later (an Excel upload) is analysed at once.
    excluded_tables: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Tables excluded from text-to-SQL analysis"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Connection creation timestamp"
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp"
    )

    def __repr__(self):
        return f"<DatabaseConnection(id={self.id}, name={self.name}, host={self.host})>"


class ExcelUpload(Base):
    """
    Tracks uploaded Excel files and their temporary PostgreSQL tables.
    Manages automatic cleanup based on TTL (time-to-live).
    """
    __tablename__ = "excel_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, comment="Original Excel filename")
    table_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="Generated temporary table name in database"
    )
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Number of rows in Excel file")
    column_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Number of columns in Excel file")
    schema_info: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Column names and inferred data types"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Upload timestamp"
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Expiration timestamp for automatic cleanup"
    )

    def __repr__(self):
        return f"<ExcelUpload(id={self.id}, filename={self.filename}, table={self.table_name})>"


class AnomalyReview(Base):
    """Reviewer's decision on one anomaly finding."""

    __tablename__ = "anomaly_review"
    __table_args__ = (UniqueConstraint("database_id", "finding_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[str] = mapped_column(String(255), nullable=False)
    finding_key: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="confirmed or dismissed")
    fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="Finding content when reviewed; a mismatch reopens it"
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class LLMSetting(Base):
    """Which LLM answers questions, as chosen on the settings screen.

    A single row (id = 1). `profiles` holds each serving platform's settings,
    {name: {base_url, model, api_key}}, so switching platforms loses nothing;
    api_key values are Fernet-encrypted. Anything never saved falls back to .env.
    """

    __tablename__ = "llm_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[Optional[str]] = mapped_column(
        String(40), nullable=True, comment="Chosen platform: ollama, lmstudio, vllm, openai_compatible, groq"
    )
    profiles: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, comment="Per-platform settings; api_key encrypted"
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class GlossaryTerm(Base):
    """A business term and what it means, e.g. 고액 = 한 건 50만원 이상.

    A question that uses the term gets the definition in its prompt, so the
    LLM writes the same condition every time instead of guessing.
    """

    __tablename__ = "glossary_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class ColumnLabel(Base):
    """The name a column is shown under, chosen by an administrator.

    `table_key` NULL means the column name on the whole connection (a table and
    the views reusing the name); a value is an exception for that one table.
    A unique index over (connection_id, coalesce(table_key, ''), column_name)
    keeps one label per scope; it is created by the migration.
    """

    __tablename__ = "column_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False
    )
    table_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    column_name: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ExpressionTerm(Base):
    """A changed name for a computed-column function (sum -> 합계). Only changes
    are stored; the defaults live in app/db/column_labels.py."""

    __tablename__ = "expression_terms"

    function: Mapped[str] = mapped_column("func", String(20), primary_key=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class User(Base):
    """A person who signs in. Roles: admin, auditor, viewer."""

    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class AuditLog(Base):
    """Who did what, and when. Append-only: nothing in the app edits or deletes it."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    username: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    target: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")


class AnomalySetting(Base):
    """Edited anomaly thresholds. A single row (id = 1); empty means the defaults
    written in app/anomaly/rules.py."""

    __tablename__ = "anomaly_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AnomalySettingHistory(Base):
    """One change to the anomaly settings: who, when, the values before and after
    (for restoring), and the readable list of what moved (for showing)."""

    __tablename__ = "anomaly_setting_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    changed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    changed_by: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    before: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    after: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    changes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class SavedReport(Base):
    """A question kept as a report that runs on a schedule and keeps its last result."""

    __tablename__ = "saved_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    database_id: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    run_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    run_weekday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    run_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_run_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_results: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class EvalCase(Base):
    """A question with its known-correct SQL, for scoring the LLM."""

    __tablename__ = "eval_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_sql: Mapped[str] = mapped_column(Text, nullable=False)
    database_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class EvalRun(Base):
    """One scoring of the whole set against the LLM chosen at the time."""

    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    provider: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    started_by: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
