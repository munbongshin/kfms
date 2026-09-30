"""
Query API endpoints.
Natural language to SQL query generation and execution.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.auth.deps import ADMIN, ANY_USER, CurrentUser, record
from app.auth.masking import mask_results
from app.dependencies import get_db, get_db_pool
from app.db.connection_pool import DatabaseConnectionPool
from app.db.repositories.history import HistoryRepository
from app.db.repositories.database_repo import DatabaseRepository
from app.db.repositories.glossary import GlossaryRepository
from app.services.llm_service import get_llm_service
from app.api.v1.llm_settings import current_llm_config
from app.llm.settings_resolver import LLMConfig
from app.services.query_service import QueryService


router = APIRouter(prefix="/query", tags=["Query"])


# Pydantic models
class GenerateRequest(BaseModel):
    """Request model for SQL generation."""
    question: str = Field(..., min_length=1, description="Natural language question")
    database_id: int = Field(..., description="Database connection ID")
    llm_provider: Optional[str] = Field(None, description="LLM provider override ('ollama' or 'groq')")
    context: str = Field(default="", description="Optional context for query generation")


class ValidateRequest(BaseModel):
    """Request model for SQL validation."""
    sql: str = Field(..., min_length=1, description="SQL query to validate")


class ExecuteRequest(BaseModel):
    """Request model for SQL execution."""
    question: str = Field(..., min_length=1, description="Original natural language question")
    sql: str = Field(..., min_length=1, description="SQL query to execute")
    database_id: int = Field(..., description="Database connection ID")
    llm_provider: Optional[str] = Field(None, description="LLM provider used")
    llm_model: Optional[str] = Field(None, description="LLM model used")
    validation_approved: bool = Field(default=True, description="User approved execution")


class GenerateAndExecuteRequest(BaseModel):
    """Request model for combined generation and execution."""
    question: str = Field(..., min_length=1, description="Natural language question")
    database_id: int = Field(..., description="Database connection ID")
    llm_provider: Optional[str] = Field(None, description="LLM provider override")
    context: str = Field(default="", description="Optional context")
    auto_approve: bool = Field(default=False, description="Skip user confirmation")


async def excluded_tables_for(database_id: int, db: AsyncSession) -> list:
    """The tables this connection leaves out of analysis (none if unknown)."""
    conn = await DatabaseRepository(db).get_by_id(database_id)
    return list(conn.excluded_tables or []) if conn else []


def get_query_service(
    db: AsyncSession = Depends(get_db),
    pool: DatabaseConnectionPool = Depends(get_db_pool),
    llm_config: LLMConfig = Depends(current_llm_config),
) -> QueryService:
    """
    Dependency for getting QueryService instance.
    """
    history_repo = HistoryRepository(db)
    # The LLM chosen on the settings screen, read per request so a change
    # applies to the next question without a restart.
    llm_service = get_llm_service(config=llm_config)
    return QueryService(
        connection_pool=pool,
        history_repo=history_repo,
        llm_service=llm_service,
        glossary_repo=GlossaryRepository(db),
    )


@router.post("/generate")
async def generate_sql(
    request: GenerateRequest,
    service: QueryService = Depends(get_query_service),
    llm_config: LLMConfig = Depends(current_llm_config),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate SQL from natural language question.

    Returns generated SQL with validation results.
    Does not execute the query.
    """
    try:
        # Override LLM provider if specified
        if request.llm_provider:
            service.llm_service = get_llm_service(request.llm_provider, llm_config)

        result = await service.generate_sql(
            question=request.question,
            database_id=str(request.database_id),
            context=request.context,
            excluded_tables=await excluded_tables_for(request.database_id, db),
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SQL: {str(e)}"
        )


@router.post("/validate")
async def validate_sql(
    request: ValidateRequest,
    service: QueryService = Depends(get_query_service)
):
    """
    Validate SQL query for safety.

    Checks for read-only compliance and dangerous operations.
    """
    try:
        validation = await service.validate_sql(request.sql)
        return validation

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        )


@router.post("/execute")
async def execute_query(
    request: ExecuteRequest,
    http_request: Request,
    user: CurrentUser = ANY_USER,
    db: AsyncSession = Depends(get_db),
    service: QueryService = Depends(get_query_service)
):
    """
    Execute SQL query and save to history.

    Validates SQL before execution.
    Requires user approval for execution.
    """
    try:
        result = await service.execute_query(
            question=request.question,
            sql=request.sql,
            database_id=str(request.database_id),
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
            validation_approved=request.validation_approved
        )

        await record(
            db, user, http_request, "query_execute", str(request.database_id),
            question=request.question[:300], sql=request.sql[:2000],
            success=bool(result.get("success")), rows=result.get("row_count"),
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Query execution failed")
            )

        # Viewers may ask questions but not read card numbers.
        result["results"] = mask_results(result["results"], user.role)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@router.post("/generate-and-execute")
async def generate_and_execute(
    request: GenerateAndExecuteRequest,
    http_request: Request,
    user: CurrentUser = ANY_USER,
    service: QueryService = Depends(get_query_service),
    llm_config: LLMConfig = Depends(current_llm_config),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate SQL and execute in one step.

    If auto_approve is False, may return generated SQL for user confirmation.
    """
    try:
        # Override LLM provider if specified
        if request.llm_provider:
            service.llm_service = get_llm_service(request.llm_provider, llm_config)

        result = await service.generate_and_execute(
            question=request.question,
            database_id=str(request.database_id),
            context=request.context,
            auto_approve=request.auto_approve,
            excluded_tables=await excluded_tables_for(request.database_id, db),
        )

        if "results" in result:
            await record(
                db, user, http_request, "query_execute", str(request.database_id),
                question=request.question[:300], sql=(result.get("generation") or {}).get("sql", "")[:2000],
                success=bool(result.get("success")), rows=result.get("row_count"),
            )
            result["results"] = mask_results(result["results"], user.role)

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Operation failed: {str(e)}"
        )
