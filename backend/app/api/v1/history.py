"""
Query History API endpoints.
View and manage query execution history.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from app.dependencies import get_db
from app.db.repositories.history import HistoryRepository


router = APIRouter(prefix="/history", tags=["History"])


# Pydantic models
class HistoryListItem(BaseModel):
    """List item for query history."""
    id: int
    question: str
    generated_sql: str
    database_id: str
    status: str
    row_count: Optional[int]
    execution_time_ms: Optional[int]
    llm_provider: Optional[str]
    llm_model: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class HistoryDetail(BaseModel):
    """Detailed query history record."""
    id: int
    question: str
    generated_sql: str
    database_id: str
    status: str
    results: Optional[list]
    error_message: Optional[str]
    execution_time_ms: Optional[int]
    row_count: Optional[int]
    llm_provider: Optional[str]
    llm_model: Optional[str]
    validation_approved: bool
    created_at: str

    class Config:
        from_attributes = True


def get_history_repo(db: AsyncSession = Depends(get_db)) -> HistoryRepository:
    """Dependency for getting HistoryRepository."""
    return HistoryRepository(db)


@router.get("", response_model=list[HistoryListItem])
async def list_history(
    database_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    repo: HistoryRepository = Depends(get_history_repo)
):
    """
    Get query history with optional filters.

    Args:
        database_id: Filter by database connection ID
        status: Filter by status (success, error, pending)
        limit: Maximum records to return (max 1000)
        offset: Number of records to skip

    Returns:
        List of query history records
    """
    # Cap limit at 1000
    limit = min(limit, 1000)

    try:
        history = await repo.get_all(
            database_id=database_id,
            status=status,
            limit=limit,
            offset=offset
        )

        return [
            HistoryListItem(
                id=h.id,
                question=h.question,
                generated_sql=h.generated_sql,
                database_id=h.database_id,
                status=h.status,
                row_count=h.row_count,
                execution_time_ms=h.execution_time_ms,
                llm_provider=h.llm_provider,
                llm_model=h.llm_model,
                created_at=h.created_at.isoformat()
            )
            for h in history
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(e)}"
        )


@router.get("/{history_id}", response_model=HistoryDetail)
async def get_history(
    history_id: int,
    repo: HistoryRepository = Depends(get_history_repo)
):
    """
    Get detailed query history record.

    Includes full results if available.
    """
    try:
        history = await repo.get_by_id(history_id)

        if not history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"History {history_id} not found"
            )

        return HistoryDetail(
            id=history.id,
            question=history.question,
            generated_sql=history.generated_sql,
            database_id=history.database_id,
            status=history.status,
            results=history.results,
            error_message=history.error_message,
            execution_time_ms=history.execution_time_ms,
            row_count=history.row_count,
            llm_provider=history.llm_provider,
            llm_model=history.llm_model,
            validation_approved=history.validation_approved,
            created_at=history.created_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get history: {str(e)}"
        )


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history(
    history_id: int,
    repo: HistoryRepository = Depends(get_history_repo)
):
    """
    Delete query history record.

    This permanently removes the history entry.
    """
    try:
        deleted = await repo.delete_history(history_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"History {history_id} not found"
            )

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete history: {str(e)}"
        )


@router.get("/stats/summary")
async def get_history_stats(
    repo: HistoryRepository = Depends(get_history_repo)
):
    """
    Get summary statistics for query history.

    Returns counts and aggregates.
    """
    try:
        all_history = await repo.get_all(limit=10000)

        total = len(all_history)
        success = len([h for h in all_history if h.status == 'success'])
        errors = len([h for h in all_history if h.status == 'error'])

        total_rows = sum(h.row_count or 0 for h in all_history if h.row_count)
        avg_time = (
            sum(h.execution_time_ms or 0 for h in all_history if h.execution_time_ms) / total
            if total > 0 else 0
        )

        return {
            "total_queries": total,
            "successful": success,
            "errors": errors,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
            "total_rows_returned": total_rows,
            "avg_execution_time_ms": round(avg_time, 1)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )
