"""
Excel API endpoints.
Upload and manage Excel files as queryable database tables.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.dependencies import get_db, get_db_pool
from app.db.connection_pool import DatabaseConnectionPool
from app.services.excel_service import ExcelService, TableNameTaken
from app.config import settings


router = APIRouter(prefix="/excel", tags=["Excel"])


# Pydantic models
class ExcelUploadResponse(BaseModel):
    """Response model for Excel upload."""
    id: int
    filename: str
    table_name: str
    row_count: int
    column_count: int
    schema: dict
    expires_at: str
    database_id: str


class ExcelListItem(BaseModel):
    """List item for Excel uploads."""
    id: int
    filename: str
    table_name: str
    row_count: int
    column_count: int
    created_at: str
    expires_at: str

    class Config:
        from_attributes = True


def get_excel_service(
    db: AsyncSession = Depends(get_db),
    pool: DatabaseConnectionPool = Depends(get_db_pool)
) -> ExcelService:
    """
    Dependency for getting ExcelService instance.
    """
    return ExcelService(session=db, connection_pool=pool)


@router.post("/upload", response_model=ExcelUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_excel(
    file: UploadFile = File(..., description="Excel file (.xls or .xlsx)"),
    database_id: int = Form(..., description="Target database connection ID"),
    ttl_hours: Optional[int] = Form(None, description="Time-to-live in hours"),
    table_name: Optional[str] = Form(None, description="Table name; the file name when omitted"),
    service: ExcelService = Depends(get_excel_service)
):
    """
    Upload Excel file and create temporary queryable table.

    The Excel file will be parsed and converted to a PostgreSQL table.
    You can then query it using natural language or SQL.

    Tables are automatically cleaned up after TTL expires (default 24 hours).
    """
    # Validate file size
    max_size = settings.EXCEL_UPLOAD_MAX_SIZE_MB * 1024 * 1024  # Convert to bytes

    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.EXCEL_UPLOAD_MAX_SIZE_MB}MB"
        )

    # Reset file pointer
    await file.seek(0)

    try:
        result = await service.upload_excel(
            file=file,
            database_id=str(database_id),
            ttl_hours=ttl_hours,
            table_name=table_name,
        )

        return result

    except TableNameTaken as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.post("/{upload_id}/extend")
async def extend_upload(
    upload_id: int,
    hours: int = 24,
    service: ExcelService = Depends(get_excel_service)
):
    """Keep an upload longer, so a table still being analysed does not expire."""
    if not 1 <= hours <= 24 * 30:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="연장 시간은 1시간에서 30일 사이여야 합니다")
    upload = await service.extend_upload(upload_id, hours)
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업로드를 찾을 수 없습니다")
    return {"id": upload.id, "expires_at": upload.expires_at.isoformat()}


@router.get("/table-name")
async def check_table_name(
    database_id: int,
    name: str,
    service: ExcelService = Depends(get_excel_service)
):
    """The table name an upload would get from `name`, and whether it is free."""
    return await service.check_table_name(str(database_id), name)


@router.get("/uploads", response_model=List[ExcelListItem])
async def list_uploads(
    service: ExcelService = Depends(get_excel_service)
):
    """
    Get all Excel uploads.

    Returns list of uploaded Excel files with metadata.
    """
    try:
        uploads = await service.get_uploads()

        return [
            ExcelListItem(
                id=u.id,
                filename=u.filename,
                table_name=u.table_name,
                row_count=u.row_count or 0,
                column_count=u.column_count or 0,
                created_at=u.created_at.isoformat(),
                expires_at=u.expires_at.isoformat() if u.expires_at else ""
            )
            for u in uploads
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list uploads: {str(e)}"
        )


@router.get("/{upload_id}/preview")
async def preview_upload(
    upload_id: int,
    database_id: int,
    limit: int = 100,
    service: ExcelService = Depends(get_excel_service)
):
    """
    Preview Excel upload data.

    Returns first N rows of the uploaded Excel table.
    """
    try:
        preview = await service.preview_upload(
            upload_id=upload_id,
            database_id=str(database_id),
            limit=min(limit, 1000)  # Cap at 1000 rows
        )

        return preview

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Preview failed: {str(e)}"
        )


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(
    upload_id: int,
    database_id: int,
    service: ExcelService = Depends(get_excel_service)
):
    """
    Delete Excel upload and drop its table.

    This permanently removes the uploaded data.
    """
    try:
        deleted = await service.delete_upload(
            upload_id=upload_id,
            database_id=str(database_id)
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Upload {upload_id} not found"
            )

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete failed: {str(e)}"
        )


@router.post("/cleanup")
async def cleanup_expired(
    database_id: int,
    service: ExcelService = Depends(get_excel_service)
):
    """
    Manually trigger cleanup of expired uploads.

    Normally this runs automatically via APScheduler.
    """
    try:
        count = await service.cleanup_expired_uploads(
            database_id=str(database_id)
        )

        return {
            "cleaned_up": count,
            "message": f"Cleaned up {count} expired upload(s)"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup failed: {str(e)}"
        )
