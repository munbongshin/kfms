"""
Excel Service for file processing.
Handles Excel upload, parsing, and temporary table creation.
"""
from typing import Dict, List, Any, Optional
import re
import unicodedata
import pandas as pd
from datetime import datetime, timedelta
import uuid
import time
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.models import ExcelUpload
from app.db.repositories.database_repo import DatabaseRepository
from app.db.connection_pool import DatabaseConnectionPool
from app.db.catalog import quote, quote_relation, table_key
from app.config import settings

# Uploads get a schema of their own in the target database, so they never mix
# with the source tables yet can still be joined with them in one question.
UPLOAD_SCHEMA = "kfms_upload"

# Rows per executemany round trip.
INSERT_BATCH = 1000


# PostgreSQL truncates identifiers past 63 bytes; a Korean character is 3.
MAX_IDENTIFIER_BYTES = 63
FALLBACK_NAME = "excel_upload"


class TableNameTaken(ValueError):
    """The chosen table name is already used; the user should pick another."""


def table_name_from(raw: str) -> str:
    """A table name from a file name (or one the user typed).

    Letters of any script, digits and underscores survive; everything else
    becomes one underscore. English is lower-cased and a leading digit or pg_
    gets a prefix, so the name also works unquoted — as the LLM tends to write
    it. Cut to PostgreSQL's 63-byte limit without splitting a character.
    """
    name = unicodedata.normalize("NFC", raw.strip())
    name = re.sub(r"\.(xlsx|xls)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[^\w]+", "_", name).strip("_").lower()
    if not name:
        return FALLBACK_NAME
    if name[0].isdigit() or name.startswith("pg_"):
        name = f"t_{name}"
    while len(name.encode("utf-8")) > MAX_IDENTIFIER_BYTES:
        name = name[:-1]
    return name.rstrip("_") or FALLBACK_NAME


def upload_table_key(table_name: str) -> str:
    """How an upload is named everywhere: kfms_upload.<table>."""
    return table_key(UPLOAD_SCHEMA, table_name)


def build_create_table(relation: str, columns: Dict[Any, str]) -> str:
    """CREATE TABLE with every identifier quoted. Headers come from the user's
    sheet — Korean, spaces, brackets, quotes — and must not break the SQL."""
    cols = ", ".join(f"{quote(str(name))} {pg_type}" for name, pg_type in columns.items())
    return f"CREATE TABLE {quote_relation(relation)} ({cols})"


def build_insert(relation: str, column_count: int) -> str:
    """INSERT bound by position. Headers make poor bind names (":총 연구기간",
    ":2023년" are invalid), positions never do."""
    params = ", ".join(f":p{i}" for i in range(column_count))
    return f"INSERT INTO {quote_relation(relation)} VALUES ({params})"


def _plain(value: Any) -> Any:
    """A value the database driver accepts: no NaN/NaT, no numpy scalars."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        return value.item()
    return value


def row_params(values: List[Any]) -> Dict[str, Any]:
    return {f"p{i}": _plain(v) for i, v in enumerate(values)}


class ExcelService:
    """
    Service for Excel file processing and temporary table management.
    """

    def __init__(
        self,
        session: AsyncSession,
        connection_pool: DatabaseConnectionPool
    ):
        """
        Initialize Excel service.

        Args:
            session: Database session for metadata
            connection_pool: Connection pool for target database
        """
        self.session = session
        self.pool = connection_pool

    async def table_name_conflict(self, database_id: str, name: str) -> Optional[str]:
        """Where `name` is already taken, or None if it is free.

        Checked in the upload schema and in public — an upload named like a
        source table would confuse people and the LLM alike — and against the
        upload records, whose table names must stay unique.
        """
        async with self.pool.get_connection(database_id) as conn:
            result = await conn.execute(
                text(
                    "SELECT n.nspname FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE c.relname = :name AND n.nspname IN (:upload, 'public') "
                    "ORDER BY n.nspname = 'public' DESC LIMIT 1"
                ),
                {"name": name, "upload": UPLOAD_SCHEMA},
            )
            schema = result.scalar()
        if schema:
            return table_key(schema, name)

        from sqlalchemy import select
        key = upload_table_key(name)
        recorded = await self.session.execute(
            select(ExcelUpload.id).where(ExcelUpload.table_name == key)
        )
        return key if recorded.scalar() else None

    async def check_table_name(self, database_id: str, requested: str) -> Dict[str, Any]:
        """The name an upload would get, and whether it is free."""
        name = table_name_from(requested)
        taken = await self.table_name_conflict(database_id, name)
        return {
            "requested": requested,
            "name": name,
            "key": upload_table_key(name),
            "available": taken is None,
            "conflict_with": taken,
        }

    async def upload_excel(
        self,
        file: UploadFile,
        database_id: str,
        ttl_hours: Optional[int] = None,
        table_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload and process Excel file.

        Args:
            file: Uploaded Excel file
            database_id: Target database connection ID
            ttl_hours: Time-to-live in hours (default from settings)

        Returns:
            Dict with upload information and table details
        """
        # Validate file type
        if not file.filename:
            raise ValueError("No filename provided")

        ext = file.filename.lower().split('.')[-1]
        if ext not in ['xls', 'xlsx']:
            raise ValueError("Only .xls and .xlsx files are supported")

        # Read Excel file
        try:
            content = await file.read()

            # Parse with pandas
            if ext == 'xlsx':
                df = pd.read_excel(content, engine='openpyxl')
            else:
                df = pd.read_excel(content, engine='xlrd')

        except Exception as e:
            raise ValueError(f"Failed to parse Excel file: {str(e)}")

        if df.empty:
            raise ValueError("Excel file is empty")

        # The table is named after the file unless the user chose a name.
        name = table_name_from(table_name or file.filename)
        taken = await self.table_name_conflict(database_id, name)
        if taken:
            raise TableNameTaken(f"'{taken}' 테이블이 이미 있습니다 — 다른 테이블 이름을 입력하세요")
        table_name = upload_table_key(name)

        # Get column information
        schema_info = self._infer_schema(df)

        # Create table in target database
        try:
            await self._create_table_from_dataframe(
                df=df,
                table_name=table_name,
                database_id=database_id,
                schema_info=schema_info
            )
        except Exception as e:
            # Taken between the check and the CREATE: still the user's call.
            if "already exists" in str(e):
                raise TableNameTaken(
                    f"'{table_name}' 테이블이 이미 있습니다 — 다른 테이블 이름을 입력하세요"
                ) from e
            raise Exception(f"Failed to create table: {str(e)}")

        # Save metadata
        ttl = ttl_hours or settings.EXCEL_TABLE_TTL_HOURS
        expires_at = datetime.utcnow() + timedelta(hours=ttl)

        upload_record = ExcelUpload(
            filename=file.filename,
            table_name=table_name,
            row_count=len(df),
            column_count=len(df.columns),
            schema_info=schema_info,
            expires_at=expires_at
        )

        self.session.add(upload_record)
        await self.session.commit()
        await self.session.refresh(upload_record)

        return {
            "id": upload_record.id,
            "filename": file.filename,
            "table_name": table_name,
            "row_count": len(df),
            "column_count": len(df.columns),
            "schema": schema_info,
            "expires_at": expires_at.isoformat(),
            "database_id": database_id
        }

    def _infer_schema(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Infer PostgreSQL column types from pandas DataFrame.

        Args:
            df: pandas DataFrame

        Returns:
            Dict mapping column names to PostgreSQL types
        """
        schema = {}

        for col in df.columns:
            dtype = df[col].dtype

            if pd.api.types.is_integer_dtype(dtype):
                schema[col] = "INTEGER"
            elif pd.api.types.is_float_dtype(dtype):
                schema[col] = "NUMERIC"
            elif pd.api.types.is_bool_dtype(dtype):
                schema[col] = "BOOLEAN"
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                schema[col] = "TIMESTAMP"
            else:
                # Default to TEXT for strings and unknown types
                schema[col] = "TEXT"

        return schema

    async def _create_table_from_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        database_id: str,
        schema_info: Dict[str, str]
    ) -> None:
        """
        Create PostgreSQL table from DataFrame.

        Args:
            df: pandas DataFrame
            table_name: Table name to create
            database_id: Database connection ID
            schema_info: Column type mapping
        """
        create_sql = build_create_table(table_name, schema_info)
        insert_sql = build_insert(table_name, len(df.columns))
        rows = [row_params(list(r)) for r in df.itertuples(index=False, name=None)]

        # Read-only connections protect questions, not KFMS's own tables:
        # this one transaction may write, everything else stays read-only.
        async with self.pool.get_write_connection(database_id) as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quote(UPLOAD_SCHEMA)}"))
            await conn.execute(text(create_sql))

            for start in range(0, len(rows), INSERT_BATCH):
                await conn.execute(text(insert_sql), rows[start:start + INSERT_BATCH])

            # The index is a nicety. A failed statement aborts the whole
            # transaction in PostgreSQL, so it runs in a savepoint: failing
            # there must not take the upload down with it.
            index_name = quote(f"idx_{table_name.split('.')[-1]}_c0")
            first_col = quote(str(df.columns[0]))
            try:
                async with conn.begin_nested():
                    await conn.execute(
                        text(f"CREATE INDEX {index_name} ON {quote_relation(table_name)} ({first_col})")
                    )
            except Exception:
                pass

        # A new table: the cached catalog no longer lists everything.
        self.pool.invalidate_schema(database_id)

    async def get_uploads(self) -> List[ExcelUpload]:
        """
        Get all Excel uploads.

        Returns:
            List of ExcelUpload records
        """
        from sqlalchemy import select
        result = await self.session.execute(
            select(ExcelUpload).order_by(ExcelUpload.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_upload_by_id(self, upload_id: int) -> Optional[ExcelUpload]:
        """
        Get Excel upload by ID.

        Args:
            upload_id: Upload ID

        Returns:
            ExcelUpload if found, None otherwise
        """
        from sqlalchemy import select
        result = await self.session.execute(
            select(ExcelUpload).where(ExcelUpload.id == upload_id)
        )
        return result.scalar_one_or_none()

    async def preview_upload(
        self,
        upload_id: int,
        database_id: str,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Preview Excel upload data.

        Args:
            upload_id: Upload ID
            database_id: Database connection ID
            limit: Number of rows to preview

        Returns:
            Dict with preview data
        """
        upload = await self.get_upload_by_id(upload_id)
        if not upload:
            raise ValueError(f"Upload {upload_id} not found")

        # Query table
        preview_sql = f"SELECT * FROM {quote_relation(upload.table_name)} LIMIT {int(limit)}"

        results = await self.pool.execute_query(
            connection_id=database_id,
            sql=preview_sql
        )

        return {
            "upload_id": upload_id,
            "filename": upload.filename,
            "table_name": upload.table_name,
            "total_rows": upload.row_count,
            "preview_rows": len(results),
            "data": results
        }

    async def delete_upload(
        self,
        upload_id: int,
        database_id: str
    ) -> bool:
        """
        Delete Excel upload and its table.

        Args:
            upload_id: Upload ID
            database_id: Database connection ID

        Returns:
            True if deleted successfully
        """
        upload = await self.get_upload_by_id(upload_id)
        if not upload:
            return False

        # Drop table from database
        try:
            drop_sql = f"DROP TABLE IF EXISTS {quote_relation(upload.table_name)}"
            async with self.pool.get_write_connection(database_id) as conn:
                await conn.execute(text(drop_sql))
            self.pool.invalidate_schema(database_id)
        except Exception as e:
            print(f"Warning: Failed to drop table {upload.table_name}: {e}")

        # Delete metadata
        from sqlalchemy import delete as sql_delete
        await self.session.execute(
            sql_delete(ExcelUpload).where(ExcelUpload.id == upload_id)
        )
        await self.session.commit()

        return True

    async def cleanup_expired_uploads(self, database_id: str) -> int:
        """
        Clean up expired Excel uploads.

        Args:
            database_id: Database connection ID

        Returns:
            Number of uploads cleaned up
        """
        from sqlalchemy import select

        # Find expired uploads
        now = datetime.utcnow()
        result = await self.session.execute(
            select(ExcelUpload).where(
                ExcelUpload.expires_at <= now
            )
        )
        expired = list(result.scalars().all())

        count = 0
        for upload in expired:
            try:
                await self.delete_upload(upload.id, database_id)
                count += 1
            except Exception as e:
                print(f"Failed to cleanup upload {upload.id}: {e}")

        return count
