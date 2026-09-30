"""
Query Service for SQL query execution.
Handles validation, execution, and history management.
"""
from typing import Dict, List, Any, Optional
import time

from app.utils.sql_validator import SQLValidator
from app.db.connection_pool import DatabaseConnectionPool
from app.db.repositories.history import HistoryRepository
from app.services.llm_service import LLMService
from app.services.plan_cost import plan_cost
from app.services.prompt_context import build_context, pick_examples, pick_terms, retry_context
from app.config import settings


# A failed dry run is fed back to the model this many times before giving up.
MAX_RETRIES = 2
# The planner's cost units; roughly a few seconds of work and up.
COST_WARNING = 1_000_000


class QueryService:
    """
    Service for managing query execution workflow.
    """

    def __init__(
        self,
        connection_pool: DatabaseConnectionPool,
        history_repo: HistoryRepository,
        llm_service: LLMService,
        glossary_repo: Optional[Any] = None,
    ):
        """
        Initialize query service.

        Args:
            connection_pool: Database connection pool
            history_repo: History repository
            llm_service: LLM service
        """
        self.pool = connection_pool
        self.history_repo = history_repo
        self.llm_service = llm_service
        self.glossary_repo = glossary_repo
        self.validator = SQLValidator()

    async def _guidance(self, question: str, database_id: str, use_examples: bool = True) -> Dict[str, Any]:
        """Bookmarked examples and glossary terms relevant to the question.
        Guidance is a bonus: failing to load it must never block a question."""
        examples: List[Any] = []
        terms: List[Any] = []
        try:
            if not use_examples:
                raise LookupError  # skip: evaluating, examples would hand over the answer
            saved = await self.history_repo.get_all(
                database_id=database_id, status="success", bookmarked=True, limit=50
            )
            examples = pick_examples(
                question, [{"question": h.question, "sql": h.generated_sql} for h in saved], k=3
            )
        except Exception:
            pass
        try:
            if self.glossary_repo is not None:
                rows = await self.glossary_repo.list_all()
                terms = pick_terms(question, [{"term": r.term, "definition": r.definition} for r in rows])
        except Exception:
            pass
        return {"examples": examples, "terms": terms}

    async def _dry_run(self, database_id: str, sql: str):
        """(the database's complaint about `sql` or None, its estimated cost).
        EXPLAIN without ANALYZE plans the query without running it."""
        try:
            rows = await self.pool.execute_query(database_id, f"EXPLAIN (FORMAT JSON) {sql}")
            return None, plan_cost(rows)
        except Exception as exc:
            # The driver wraps the server message; the first line is the useful part.
            return str(exc).strip().splitlines()[0][:400], None

    async def generate_sql(
        self,
        question: str,
        database_id: str,
        context: str = "",
        excluded_tables: Optional[List[str]] = None,
        previous: Optional[Dict[str, str]] = None,
        use_examples: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language question.

        Args:
            question: User's question
            database_id: Database connection ID
            context: Optional context

        Returns:
            Dict with generated SQL and validation results
        """
        guidance = await self._guidance(question, database_id, use_examples)
        base_context = build_context(context, guidance["examples"], guidance["terms"], previous)

        # Generate, then check the SQL plans cleanly; if it does not, hand the
        # database's error back to the model, up to MAX_RETRIES times.
        attempt_context = base_context
        attempts = 0
        db_error: Optional[str] = None
        cost = None
        while True:
            attempts += 1
            llm_result = await self.llm_service.generate_sql(
                question=question,
                connection_pool=self.pool,
                database_id=database_id,
                context=attempt_context,
                excluded_tables=excluded_tables,
            )
            sql = llm_result["sql"]
            validation = self.validator.validate(sql)

            if not validation["is_safe"]:
                sql_with_limit = sql
                break

            sql_with_limit = self.validator.enforce_limit(sql, settings.QUERY_RESULT_LIMIT)
            db_error, cost = await self._dry_run(database_id, sql_with_limit)
            if db_error is None or attempts > MAX_RETRIES:
                break
            attempt_context = "\n\n".join(
                p for p in (base_context, retry_context(sql, db_error)) if p
            )

        if cost and cost[0] > COST_WARNING:
            validation = dict(validation)
            validation["warnings"] = list(validation.get("warnings", [])) + [
                f"실행 비용이 큰 쿼리입니다(예상 {cost[1]:,}행). 오래 걸리거나 시간 제한(약 {settings.QUERY_TIMEOUT}초)에 걸릴 수 있습니다."
            ]

        if db_error is not None:
            validation = dict(validation)
            validation["warnings"] = list(validation.get("warnings", [])) + [
                f"이 SQL은 실행 전 검사에서 오류가 났습니다: {db_error}"
            ]

        return {
            "question": question,
            "sql": sql_with_limit,
            "original_sql": sql,
            "validation": validation,
            "llm_provider": llm_result["provider"],
            "llm_model": llm_result["model"],
            # How the answer was reached: retries, and what guided the model.
            "attempts": attempts,
            "follow_up": bool(previous and previous.get("sql")),
            "examples_used": len(guidance["examples"]),
            "terms_used": [t["term"] for t in guidance["terms"]],
        }

    async def validate_sql(self, sql: str) -> Dict[str, Any]:
        """
        Validate SQL query for safety.

        Args:
            sql: SQL query to validate

        Returns:
            Validation results
        """
        return self.validator.validate(sql)

    async def execute_query(
        self,
        question: str,
        sql: str,
        database_id: str,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        validation_approved: bool = True
    ) -> Dict[str, Any]:
        """
        Execute SQL query and save to history.

        Args:
            question: Original question
            sql: SQL query to execute
            database_id: Database connection ID
            llm_provider: LLM provider used
            llm_model: LLM model used
            validation_approved: Whether user approved execution

        Returns:
            Dict with execution results
        """
        # Validate SQL first
        validation = self.validator.validate(sql)

        if not validation["is_safe"]:
            # Create history record with error
            history = await self.history_repo.create(
                question=question,
                generated_sql=sql,
                database_id=database_id,
                llm_provider=llm_provider,
                llm_model=llm_model
            )

            await self.history_repo.update_execution_result(
                history_id=history.id,
                status="error",
                error_message="; ".join(validation["warnings"]),
                validation_approved=False
            )

            return {
                "success": False,
                "error": "SQL validation failed",
                "warnings": validation["warnings"],
                "history_id": history.id
            }

        # Create history record
        history = await self.history_repo.create(
            question=question,
            generated_sql=sql,
            database_id=database_id,
            llm_provider=llm_provider,
            llm_model=llm_model
        )

        # Execute query
        start_time = time.time()
        try:
            results = await self.pool.execute_query(
                connection_id=database_id,
                sql=sql
            )
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Limit results to configured max
            limited_results = results[:settings.QUERY_RESULT_LIMIT]
            row_count = len(results)

            # Update history with success
            await self.history_repo.update_execution_result(
                history_id=history.id,
                status="success",
                results=limited_results,
                execution_time_ms=execution_time_ms,
                row_count=row_count,
                validation_approved=validation_approved
            )

            return {
                "success": True,
                "results": limited_results,
                "row_count": row_count,
                "execution_time_ms": execution_time_ms,
                "history_id": history.id,
                "warnings": validation.get("warnings", [])
            }

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Update history with error
            await self.history_repo.update_execution_result(
                history_id=history.id,
                status="error",
                error_message=str(e),
                execution_time_ms=execution_time_ms,
                validation_approved=validation_approved
            )

            return {
                "success": False,
                "error": str(e),
                "execution_time_ms": execution_time_ms,
                "history_id": history.id
            }

    async def generate_and_execute(
        self,
        question: str,
        database_id: str,
        context: str = "",
        auto_approve: bool = False,
        excluded_tables: Optional[List[str]] = None,
        previous: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate SQL and execute in one step.

        Args:
            question: User's question
            database_id: Database connection ID
            context: Optional context
            auto_approve: Whether to skip user confirmation

        Returns:
            Dict with generation and execution results
        """
        # Generate SQL
        gen_result = await self.generate_sql(
            question=question,
            database_id=database_id,
            context=context,
            excluded_tables=excluded_tables,
            previous=previous,
        )

        # If not safe and auto_approve is False, return for user confirmation
        if not gen_result["validation"]["is_safe"] and not auto_approve:
            return {
                "success": False,
                "requires_approval": True,
                "generation": gen_result,
                "message": "SQL requires user approval before execution"
            }

        # Execute query
        exec_result = await self.execute_query(
            question=question,
            sql=gen_result["sql"],
            database_id=database_id,
            llm_provider=gen_result["llm_provider"],
            llm_model=gen_result["llm_model"],
            validation_approved=auto_approve
        )

        # Combine results
        return {
            **exec_result,
            "generation": gen_result
        }
