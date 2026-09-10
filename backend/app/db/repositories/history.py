"""
Repository for query_history table.
Handles CRUD operations for query execution history.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, desc
from datetime import datetime

from app.db.models import QueryHistory


class HistoryRepository:
    """Repository for managing query execution history."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        question: str,
        generated_sql: str,
        database_id: str,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None
    ) -> QueryHistory:
        """
        Create a new query history record.

        Args:
            question: User's natural language question
            generated_sql: LLM-generated SQL
            database_id: Database connection ID
            llm_provider: LLM provider used
            llm_model: LLM model used

        Returns:
            Created QueryHistory instance
        """
        history = QueryHistory(
            question=question,
            generated_sql=generated_sql,
            database_id=database_id,
            status='pending',
            llm_provider=llm_provider,
            llm_model=llm_model
        )

        self.session.add(history)
        await self.session.commit()
        await self.session.refresh(history)

        return history

    async def update_execution_result(
        self,
        history_id: int,
        status: str,
        results: Optional[List[Dict[str, Any]]] = None,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        row_count: Optional[int] = None,
        validation_approved: bool = False
    ) -> Optional[QueryHistory]:
        """
        Update query history with execution results.

        Args:
            history_id: History record ID
            status: Execution status ('success' or 'error')
            results: Query results (limited to first 1000 rows)
            error_message: Error details if failed
            execution_time_ms: Execution time in milliseconds
            row_count: Total number of rows returned
            validation_approved: Whether user approved execution

        Returns:
            Updated QueryHistory if found, None otherwise
        """
        stmt = (
            update(QueryHistory)
            .where(QueryHistory.id == history_id)
            .values(
                status=status,
                results=results,
                error_message=error_message,
                execution_time_ms=execution_time_ms,
                row_count=row_count,
                validation_approved=validation_approved
            )
            .returning(QueryHistory)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.scalar_one_or_none()

    async def get_by_id(self, history_id: int) -> Optional[QueryHistory]:
        """
        Get query history by ID.

        Args:
            history_id: History record ID

        Returns:
            QueryHistory if found, None otherwise
        """
        result = await self.session.execute(
            select(QueryHistory).where(QueryHistory.id == history_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        database_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[QueryHistory]:
        """
        Get query history with filters.

        Args:
            database_id: Filter by database ID
            status: Filter by status
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of QueryHistory records
        """
        query = select(QueryHistory).order_by(desc(QueryHistory.created_at))

        if database_id:
            query = query.where(QueryHistory.database_id == database_id)

        if status:
            query = query.where(QueryHistory.status == status)

        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_history(self, history_id: int) -> bool:
        """
        Delete query history record.

        Args:
            history_id: History record ID

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(QueryHistory).where(QueryHistory.id == history_id)
        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount > 0
