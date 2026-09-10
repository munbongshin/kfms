"""
Excel Service for file processing.
Handles Excel upload, parsing, and temporary table creation.
"""
from typing import Dict, List, Any, Optional
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
from app.config import settings


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

    async def upload_excel(
        self,
        file: UploadFile,
        database_id: str,
        ttl_hours: Optional[int] = None
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

        # Generate unique table name
        timestamp = int(time.time())
        unique_id = uuid.uuid4().hex[:8]
        table_name = f"excel_upload_{timestamp}_{unique_id}"

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
        # Build CREATE TABLE statement
        columns_sql = []
        for col, pg_type in schema_info.items():
            # Sanitize column name
            safe_col = f'"{col}"'
            columns_sql.append(f"{safe_col} {pg_type}")

        create_sql = f"""
        CREATE TABLE {table_name} (
            {', '.join(columns_sql)}
        )
        """

        async with self.pool.get_connection(database_id) as conn:
            # Create table
            await conn.execute(text(create_sql))

            # Insert data in batches
            batch_size = 1000
            for i in range(0, len(df), batch_size):
                batch = df.iloc[i:i + batch_size]

                # Build INSERT statement
                placeholders = ', '.join([f':{col}' for col in df.columns])
                insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders})"

                # Convert batch to list of dicts
                records = batch.to_dict('records')

                # Execute batch insert
                for record in records:
                    # Handle NaN/None values
                    clean_record = {
                        k: (None if pd.isna(v) else v)
                        for k, v in record.items()
                    }
                    await conn.execute(text(insert_sql), clean_record)

            # Create index on first column (assumed primary key)
            first_col = f'"{df.columns[0]}"'
            index_name = f"idx_{table_name}_{df.columns[0][:20]}"
            index_sql = f"CREATE INDEX {index_name} ON {table_name}({first_col})"

            try:
                await conn.execute(text(index_sql))
            except:
                pass  # Index creation is optional

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
        preview_sql = f"SELECT * FROM {upload.table_name} LIMIT {limit}"

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
            drop_sql = f"DROP TABLE IF EXISTS {upload.table_name}"
            async with self.pool.get_connection(database_id) as conn:
                await conn.execute(text(drop_sql))
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
