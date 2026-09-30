"""
Database management API endpoints.
CRUD operations for database connections.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.auth.deps import ADMIN, ANY_USER, CurrentUser, record
from app.auth.masking import mask_results
from app.dependencies import get_db, get_db_pool
from app.db.repositories.database_repo import DatabaseRepository
from app.db.connection_pool import DatabaseConnectionPool
from app.services.table_browser import MAX_PAGE_SIZE, TableBrowser
from app.services.connection_rules import is_metadata_database, needs_pool_refresh
from app.config import settings

METADATA_DB_REFUSED = (
    "KFMS 운영 정보 DB는 조회 대상으로 등록할 수 없습니다 — 모든 연결의 접속 정보가 들어 있습니다"
)


logger = logging.getLogger(__name__)

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


@router.post("", response_model=DatabaseConnectionResponse, status_code=status.HTTP_201_CREATED, dependencies=[ADMIN])
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

    if is_metadata_database(
        connection_data.host, connection_data.port, connection_data.database, settings.DATABASE_URL
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=METADATA_DB_REFUSED)

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


@router.post("/{connection_id}/test", dependencies=[ADMIN])
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
    refresh: bool = False,
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
        tables, schema = await pool.get_catalog(str(connection_id), refresh=refresh)
        excluded = set(db_conn.excluded_tables or [])
        return {
            "connection_id": connection_id,
            "connection_name": db_conn.name,
            "schema": schema,
            # Kind, description and whether each table is analysed.
            "tables": {
                key: {**info, "excluded": key in excluded, "column_count": len(schema.get(key, []))}
                for key, info in tables.items()
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch schema: {str(e)}"
        )


class AnalysisTargets(BaseModel):
    """Tables to leave out of analysis; every other table is analysed."""
    excluded: List[str]


@router.put("/{connection_id}/excluded-tables", dependencies=[ADMIN])
async def set_excluded_tables(
    connection_id: int,
    targets: AnalysisTargets,
    db: AsyncSession = Depends(get_db),
    pool: DatabaseConnectionPool = Depends(get_db_pool)
):
    """Choose which tables text-to-SQL may use. Stored per connection."""
    repo = DatabaseRepository(db)
    db_conn = await repo.get_by_id(connection_id)
    if not db_conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Connection {connection_id} not found")

    tables = await pool.get_tables(str(connection_id))
    unknown = [t for t in targets.excluded if t not in tables]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"없는 테이블입니다: {', '.join(unknown)}",
        )
    if tables and len(set(targets.excluded)) >= len(tables):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="분석 대상 테이블을 하나 이상 남겨 두세요",
        )

    # Keep the catalog's order so the stored list reads like the table list.
    wanted = set(targets.excluded)
    excluded = [t for t in tables if t in wanted]
    await repo.update_connection(connection_id, excluded_tables=excluded)
    return {"excluded": excluded, "analysed": len(tables) - len(excluded), "total": len(tables)}


@router.get("/{connection_id}/tables/{table}/rows")
async def read_table_rows(
    connection_id: int,
    table: str,
    columns: Optional[str] = Query(None, description="Comma-separated; omit for all"),
    order_by: Optional[str] = None,
    descending: bool = False,
    limit: int = Query(100, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    http_request: Request = None,
    user: CurrentUser = ANY_USER,
    db: AsyncSession = Depends(get_db),
    pool: DatabaseConnectionPool = Depends(get_db_pool),
):
    """One page of a table, with the caller's choice of columns.

    The table and column names are checked against the connection's real schema
    before any of them reach the SQL — they cannot be bound as parameters.
    """
    selected = [c for c in (columns or "").split(",") if c]

    try:
        page = await TableBrowser(pool).read_page(
            str(connection_id), table, selected, order_by, descending, limit, offset
        )
        page["rows"] = mask_results(page["rows"], user.role)
        await record(db, user, http_request, "table_preview", f"{connection_id}:{table}", offset=offset, limit=limit)
        return page
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        logger.exception(
            "Table read failed for connection_id=%s table=%s", connection_id, table
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="테이블을 읽지 못했습니다 — 서버 로그를 확인하세요",
        )


@router.patch("/{connection_id}", response_model=DatabaseConnectionResponse, dependencies=[ADMIN])
async def update_connection(
    connection_id: int,
    changes: DatabaseConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    pool: DatabaseConnectionPool = Depends(get_db_pool)
):
    """Change a connection: its name, where it points, or its credentials.

    Only the fields sent are changed. A rename leaves the live pool alone;
    anything baked into the engine (host, credentials, read-only...) rebuilds it.
    """
    repo = DatabaseRepository(db)
    current = await repo.get_by_id(connection_id)
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found"
        )

    fields = changes.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="변경할 항목이 없습니다")

    if "name" in fields and fields["name"] != current.name:
        existing = await repo.get_by_name(fields["name"])
        if existing and existing.id != connection_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{fields['name']}' 이름의 연결이 이미 있습니다"
            )

    if is_metadata_database(
        fields.get("host", current.host),
        fields.get("port", current.port),
        fields.get("database", current.database),
        settings.DATABASE_URL,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=METADATA_DB_REFUSED)

    updated = await repo.update_connection(connection_id, **fields)

    if needs_pool_refresh(fields):
        await pool.remove_connection(str(connection_id))
        if updated.is_active:
            await pool.add_connection(
                connection_id=str(updated.id),
                host=updated.host,
                port=updated.port,
                database=updated.database,
                username=updated.username,
                password=repo.get_decrypted_password(updated),
                is_read_only=updated.is_read_only
            )

    return DatabaseConnectionResponse(
        id=updated.id,
        name=updated.name,
        host=updated.host,
        port=updated.port,
        database=updated.database,
        username=updated.username,
        is_active=updated.is_active,
        is_read_only=updated.is_read_only,
        created_at=updated.created_at.isoformat(),
        updated_at=updated.updated_at.isoformat()
    )


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[ADMIN])
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
