"""
Multi-database connection pool manager.
Manages async SQLAlchemy engines for multiple PostgreSQL databases.
"""
from typing import Dict, Optional, Any, List
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection
from sqlalchemy import text, inspect
from contextlib import asynccontextmanager
from urllib.parse import quote_plus
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID
import asyncio

from app.config import settings


def _json_safe(value: Any) -> Any:
    """Driver types that json.dumps rejects, notably NUMERIC -> Decimal."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


class DatabaseConnectionPool:
    """
    Manages multiple PostgreSQL database connections with connection pooling.
    Each database gets its own async engine with configurable pool settings.
    """

    def __init__(self):
        self._engines: Dict[str, AsyncEngine] = {}
        self._lock = asyncio.Lock()

    async def add_connection(
        self,
        connection_id: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        is_read_only: bool = True,
        pool_size: int = 5,
        max_overflow: int = 10
    ) -> None:
        """
        Add a new database connection to the pool.

        Args:
            connection_id: Unique identifier for this connection
            host: Database host address
            port: Database port
            database: Database name
            username: Database username
            password: Database password (decrypted)
            is_read_only: Whether to enforce read-only mode
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
        """
        async with self._lock:
            # ssl=disable is required: asyncpg otherwise probes the default client-cert
            # path under the user's home directory, and a non-ASCII home path makes
            # load_cert_chain fail with OSError 42.
            url = (
                f"postgresql+asyncpg://{quote_plus(username)}:{quote_plus(password)}"
                f"@{host}:{port}/{database}?ssl=disable"
            )

            connect_args: Dict[str, Any] = {}

            if is_read_only:
                connect_args["server_settings"] = {
                    "default_transaction_read_only": "on"
                }

            # Create async engine with pooling
            engine = create_async_engine(
                url,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                pool_pre_ping=True,  # Verify connections before using
                echo=settings.DEBUG,
                connect_args=connect_args,
            )

            self._engines[connection_id] = engine

    async def remove_connection(self, connection_id: str) -> None:
        """
        Remove a database connection and dispose of its engine.

        Args:
            connection_id: Connection identifier to remove
        """
        async with self._lock:
            engine = self._engines.pop(connection_id, None)
            if engine:
                await engine.dispose()

    def get_engine(self, connection_id: str) -> Optional[AsyncEngine]:
        """
        Get the async engine for a specific connection.

        Args:
            connection_id: Connection identifier

        Returns:
            AsyncEngine if exists, None otherwise
        """
        return self._engines.get(connection_id)

    @asynccontextmanager
    async def get_connection(self, connection_id: str):
        """
        Get an async database connection from the pool.

        Args:
            connection_id: Connection identifier

        Yields:
            AsyncConnection

        Raises:
            ValueError: If connection_id doesn't exist
        """
        engine = self.get_engine(connection_id)
        if not engine:
            raise ValueError(f"Database connection '{connection_id}' not found")

        async with engine.begin() as conn:
            yield conn

    async def test_connection(self, connection_id: str) -> Dict[str, Any]:
        """
        Test if a database connection is working.

        Args:
            connection_id: Connection identifier

        Returns:
            Dict with status and metadata

        Raises:
            ValueError: If connection_id doesn't exist
        """
        try:
            async with self.get_connection(connection_id) as conn:
                # Simple query to test connection
                result = await conn.execute(text("SELECT version(), current_database(), current_user"))
                row = result.first()

                return {
                    "status": "success",
                    "version": row[0] if row else None,
                    "database": row[1] if row else None,
                    "user": row[2] if row else None,
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_schema(self, connection_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get database schema information (tables and columns).

        Args:
            connection_id: Connection identifier

        Returns:
            Dict mapping table names to column information

        Raises:
            ValueError: If connection_id doesn't exist
        """
        schema_info = {}

        async with self.get_connection(connection_id) as conn:
            # Get all tables in public schema
            result = await conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """))

            tables = [row[0] for row in result]

            # Get columns for each table
            for table in tables:
                result = await conn.execute(text(f"""
                    SELECT
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                    ORDER BY ordinal_position
                """), {"table_name": table})

                columns = [
                    {
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[2] == "YES",
                        "default": row[3]
                    }
                    for row in result
                ]

                schema_info[table] = columns

        return schema_info

    async def execute_query(
        self,
        connection_id: str,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a SQL query and return results.

        Args:
            connection_id: Connection identifier
            sql: SQL query to execute
            params: Optional query parameters

        Returns:
            List of result rows as dictionaries

        Raises:
            ValueError: If connection_id doesn't exist
        """
        async with self.get_connection(connection_id) as conn:
            result = await conn.execute(text(sql), params or {})

            # Convert rows to dictionaries
            rows = []
            for row in result:
                rows.append({k: _json_safe(v) for k, v in row._mapping.items()})

            return rows

    async def close_all(self) -> None:
        """
        Close all database connections and dispose of engines.
        Should be called on application shutdown.
        """
        async with self._lock:
            for engine in self._engines.values():
                await engine.dispose()
            self._engines.clear()

    def list_connections(self) -> List[str]:
        """
        Get list of all connection IDs.

        Returns:
            List of connection identifiers
        """
        return list(self._engines.keys())


# Global connection pool instance
_connection_pool: Optional[DatabaseConnectionPool] = None


def get_connection_pool() -> DatabaseConnectionPool:
    """
    Get or create the global database connection pool.

    Returns:
        DatabaseConnectionPool instance
    """
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = DatabaseConnectionPool()
    return _connection_pool
