"""
Database management API endpoints.
CRUD operations for database connections.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.dependencies import get_db, get_db_pool
from app.db.repositories.database_repo import DatabaseRepository
from app.db.connection_pool import DatabaseConnectionPool


router = APIRouter(prefix="/databases", tags=["Databases"])


# Pydantic models for request/response
class DatabaseConnectionCreate(BaseModel):
    """Request model for creating database connection."""
    name: str = Field(..., min_length=1, max_length=255, description="Connection name")
    host: str = Field(..., min_length=1, max_length=255, description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    database: str = Field(..., min_length=1, max_length=255, description="Database name")
    username: str = Field(..., min_length=1, max_length=255, description="Database username")
    password: str = Field(..., min_length=1, description="Database password (will be encrypted)")
    is_active: bool = Field(default=True, description="Connection enabled status")
    is_read_only: bool = Field(default=True, description="Enforce read-only mode")


class DatabaseConnectionUpdate(BaseModel):
    """Request model for updating database connection."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    host: Optional[str] = Field(None, min_length=1, max_length=255)
    port: Optional[int] = Field(None, ge=1, le=65535)
    database: Optional[str] = Field(None, min_length=1, max_length=255)
    username: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=1)
    is_active: Optional[bool] = None
    is_read_only: Optional[bool] = None


class DatabaseConnectionResponse(BaseModel):
    """Response model for database connection (without password)."""
    id: int
    name: str
    host: str
    port: int
    database: str
    username: str
    is_active: bool
    is_read_only: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[DatabaseConnectionResponse])
async def list_connections(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all database connections.

    Args:
        active_only: Filter for active connections only
        db: Database session

    Returns:
        List of database connections (passwords excluded)
    """
    repo = DatabaseRepository(db)
    connections = await repo.get_all(active_only=active_only)

    return [
        DatabaseConnectionResponse(
            id=conn.id,
            name=conn.name,
            host=conn.host,
            port=conn.port,
            database=conn.database,
            username=conn.username,
            is_active=conn.is_active,
            is_read_only=conn.is_read_only,
            created_at=conn.created_at.isoformat(),
            updated_at=conn.updated_at.isoformat()
        )
        for conn in connections
    ]


@router.post("", response_model=DatabaseConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    connection_data: DatabaseConnectionCreate,
    db: AsyncSession = Depends(get_db),
    pool: DatabaseConnectionPool = Depends(get_db_pool)
):
    """
    Create a new database connection.

    Args:
        connection_data: Connection configuration
        db: Database session
        pool: Connection pool

    Returns:
        Created database connection

    Raises:
        HTTPException: If connection name already exists
    """
    repo = DatabaseRepository(db)

    # Check if name already exists
    existing = await repo.get_by_name(connection_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection with name '{connection_data.name}' already exists"
        )

    # Create connection in database
    db_conn = await repo.create(
        name=connection_data.name,
        host=connection_data.host,
        port=connection_data.port,
        database=connection_data.database,
        username=connection_data.username,
        password=connection_data.password,
        is_active=connection_data.is_active,
        is_read_only=connection_data.is_read_only
    )

    # Add to connection pool if active
    if db_conn.is_active:
        try:
            await pool.add_connection(
                connection_id=str(db_conn.id),
                host=db_conn.host,
                port=db_conn.port,
                database=db_conn.database,
                username=db_conn.username,
                password=repo.get_decrypted_password(db_conn),
                is_read_only=db_conn.is_read_only
            )
        except Exception as e:
            # Rollback database creation if pool addition fails
            await repo.delete_connection(db_conn.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to add connection to pool: {str(e)}"
            )

    return DatabaseConnectionResponse(
        id=db_conn.id,
        name=db_conn.name,
        host=db_conn.host,
        port=db_conn.port,
        database=db_conn.database,
        username=db_conn.username,
        is_active=db_conn.is_active,
        is_read_only=db_conn.is_read_only,
        created_at=db_conn.created_at.isoformat(),
        updated_at=db_conn.updated_at.isoformat()
    )


@router.post("/{connection_id}/test")
async def test_connection(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    pool: DatabaseConnectionPool = Depends(get_db_pool)
):
    """
    Test a database connection.

    Args:
        connection_id: Connection ID to test
        db: Database session
        pool: Connection pool

    Returns:
        Test results with connection metadata

    Raises:
        HTTPException: If connection not found
    """
    repo = DatabaseRepository(db)
    db_conn = await repo.get_by_id(connection_id)

    if not db_conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found"
        )

    # Add to pool temporarily if not already there
    conn_id_str = str(connection_id)
    if not pool.get_engine(conn_id_str):
        await pool.add_connection(
            connection_id=conn_id_str,
            host=db_conn.host,
            port=db_conn.port,
            database=db_conn.database,
            username=db_conn.username,
            password=repo.get_decrypted_password(db_conn),
            is_read_only=db_conn.is_read_only
        )

    # Test connection
    result = await pool.test_connection(conn_id_str)

    # Remove from pool if it wasn't active
    if not db_conn.is_active:
        await pool.remove_connection(conn_id_str)

    return result


@router.get("/{connection_id}/schema")
async def get_schema(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    pool: DatabaseConnectionPool = Depends(get_db_pool)
):
    """
    Get database schema (tables and columns).

    Args:
        connection_id: Connection ID
        db: Database session
        pool: Connection pool

    Returns:
        Schema information

    Raises:
        HTTPException: If connection not found or inactive
    """
    repo = DatabaseRepository(db)
    db_conn = await repo.get_by_id(connection_id)

    if not db_conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found"
        )

    if not db_conn.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection is not active"
        )

    try:
        schema = await pool.get_schema(str(connection_id))
        return {
            "connection_id": connection_id,
            "connection_name": db_conn.name,
            "schema": schema
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch schema: {str(e)}"
        )


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    pool: DatabaseConnectionPool = Depends(get_db_pool)
):
    """
    Delete a database connection.

    Args:
        connection_id: Connection ID to delete
        db: Database session
        pool: Connection pool

    Raises:
        HTTPException: If connection not found
    """
    repo = DatabaseRepository(db)

    # Remove from pool first
    await pool.remove_connection(str(connection_id))

    # Delete from database
    deleted = await repo.delete_connection(connection_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found"
        )

    return None
