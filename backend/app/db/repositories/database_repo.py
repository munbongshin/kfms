"""
Repository for database_connections table.
Handles CRUD operations for database connection configurations.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import datetime, timezone

from app.db.models import DatabaseConnection
from app.utils.crypto import encrypt_password, decrypt_password


class DatabaseRepository:
    """Repository for managing database connections."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        name: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        is_active: bool = True,
        is_read_only: bool = True
    ) -> DatabaseConnection:
        """
        Create a new database connection.

        Args:
            name: Connection name (must be unique)
            host: Database host
            port: Database port
            database: Database name
            username: Database username
            password: Plain text password (will be encrypted)
            is_active: Whether connection is active
            is_read_only: Whether to enforce read-only mode

        Returns:
            Created DatabaseConnection instance
        """
        # Encrypt password before storing
        encrypted_password = encrypt_password(password)

        db_conn = DatabaseConnection(
            name=name,
            host=host,
            port=port,
            database=database,
            username=username,
            password=encrypted_password,
            is_active=is_active,
            is_read_only=is_read_only
        )

        self.session.add(db_conn)
        await self.session.commit()
        await self.session.refresh(db_conn)

        return db_conn

    async def get_by_id(self, connection_id: int) -> Optional[DatabaseConnection]:
        """
        Get database connection by ID.

        Args:
            connection_id: Connection ID

        Returns:
            DatabaseConnection if found, None otherwise
        """
        result = await self.session.execute(
            select(DatabaseConnection).where(DatabaseConnection.id == connection_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[DatabaseConnection]:
        """
        Get database connection by name.

        Args:
            name: Connection name

        Returns:
            DatabaseConnection if found, None otherwise
        """
        result = await self.session.execute(
            select(DatabaseConnection).where(DatabaseConnection.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all(self, active_only: bool = False) -> List[DatabaseConnection]:
        """
        Get all database connections.

        Args:
            active_only: If True, return only active connections

        Returns:
            List of DatabaseConnection instances
        """
        query = select(DatabaseConnection).order_by(DatabaseConnection.created_at.desc())

        if active_only:
            query = query.where(DatabaseConnection.is_active == True)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_connection(
        self,
        connection_id: int,
        **kwargs
    ) -> Optional[DatabaseConnection]:
        """
        Update database connection.

        Args:
            connection_id: Connection ID
            **kwargs: Fields to update

        Returns:
            Updated DatabaseConnection if found, None otherwise
        """
        # Encrypt password if provided
        if "password" in kwargs:
            kwargs["password"] = encrypt_password(kwargs["password"])

        # Update timestamp
        kwargs["updated_at"] = datetime.now(timezone.utc)

        stmt = (
            update(DatabaseConnection)
            .where(DatabaseConnection.id == connection_id)
            .values(**kwargs)
            .returning(DatabaseConnection)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.scalar_one_or_none()

    async def delete_connection(self, connection_id: int) -> bool:
        """
        Delete database connection.

        Args:
            connection_id: Connection ID

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(DatabaseConnection).where(DatabaseConnection.id == connection_id)
        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount > 0

    def get_decrypted_password(self, db_conn: DatabaseConnection) -> str:
        """
        Get decrypted password from DatabaseConnection.

        Args:
            db_conn: DatabaseConnection instance

        Returns:
            Decrypted password
        """
        return decrypt_password(db_conn.password)
