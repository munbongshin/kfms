"""
SQLAlchemy models for KFMS application.
Defines database schema for query history, database connections, and Excel uploads.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, Integer, String, Text, TIMESTAMP, JSON
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
