"""
LLM Service for orchestrating LLM provider calls.
Handles SQL generation and visualization recommendations.
"""
from typing import Dict, List, Any, Optional

from app.llm.factory import create_provider
from app.llm.base import BaseLLMProvider
from app.llm.settings_resolver import LLMConfig
from app.db.connection_pool import DatabaseConnectionPool


def analysis_schema(
    schema: Dict[str, List[Dict[str, Any]]],
    excluded: Optional[List[str]],
) -> Dict[str, List[Dict[str, Any]]]:
    """The schema a question is asked against: every table the connection can
    read, minus those excluded from analysis on the data screen. Nothing else is
    dropped automatically — a table its views cover may still be the one a
    question needs. A stale exclusion (a dropped table) is harmless."""
    dropped = set(excluded or [])
    kept = {name: cols for name, cols in schema.items() if name not in dropped}
    if not kept:
        raise ValueError(
            "분석 대상 테이블이 없습니다 — 데이터 화면의 '분석 대상'에서 테이블을 선택하세요"
        )
    return kept


class LLMService:
    """
    Service for managing LLM operations.
    """

    def __init__(self, provider_type: Optional[str] = None, config: Optional[LLMConfig] = None):
        """
        Initialize LLM service.

        Args:
            provider_type: LLM provider type ('ollama' or 'groq')
                          If None, uses the configured provider
            config: Settings chosen on the settings screen; .env when omitted
        """
        self.provider: BaseLLMProvider = create_provider(provider_type, config)

    async def generate_sql(
        self,
        question: str,
        connection_pool: DatabaseConnectionPool,
        database_id: str,
        context: str = "",
        excluded_tables: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language question.

        Args:
            question: User's natural language question
            connection_pool: Database connection pool
            database_id: Database connection ID
            context: Optional context (previous queries, hints)
            excluded_tables: Tables excluded from analysis for this connection

        Returns:
            Dict with generated SQL and metadata:
            {
                "sql": str,
                "provider": str,
                "model": str,
                "schema_used": Dict
            }

        Raises:
            ValueError: If database not found or inactive
            Exception: If SQL generation fails
        """
        # Get database schema
        try:
            schema = await connection_pool.get_schema(database_id)
        except Exception as e:
            raise ValueError(f"Failed to fetch schema for database {database_id}: {str(e)}")

        if not schema:
            raise ValueError(f"No schema found for database {database_id}")

        schema = analysis_schema(schema, excluded_tables)
        tables = await connection_pool.get_tables(database_id)
        table_comments = {
            name: info["comment"] for name, info in tables.items()
            if name in schema and info.get("comment")
        }

        # Generate SQL using LLM
        try:
            sql = await self.provider.generate_sql(
                question=question,
                schema=schema,
                context=context,
                table_comments=table_comments,
            )

            return {
                "sql": sql,
                "provider": self.provider.name,
                "model": self.provider.model,
                "schema_used": schema
            }
        except Exception as e:
            raise Exception(f"Failed to generate SQL: {str(e)}")

    async def recommend_visualization(
        self,
        sql: str,
        results: List[Dict[str, Any]],
        max_sample: int = 10
    ) -> Dict[str, Any]:
        """
        Recommend visualization type based on query and results.

        Args:
            sql: SQL query that was executed
            results: Query results
            max_sample: Maximum rows to send to LLM

        Returns:
            Visualization recommendation:
            {
                "chart_type": str,
                "x_axis": str,
                "y_axis": str,
                "reasoning": str
            }
        """
        if not results:
            return {
                "chart_type": "table",
                "x_axis": None,
                "y_axis": None,
                "reasoning": "No results to visualize"
            }

        try:
            recommendation = await self.provider.recommend_visualization(
                sql=sql,
                result_sample=results[:max_sample]
            )

            return recommendation
        except Exception as e:
            # Fallback to table on error
            return {
                "chart_type": "table",
                "x_axis": None,
                "y_axis": None,
                "reasoning": f"Error generating recommendation: {str(e)}"
            }

    async def test_connection(self) -> bool:
        """
        Test if LLM provider is available.

        Returns:
            True if provider is available
        """
        try:
            return await self.provider.validate_connection()
        except Exception:
            return False


def get_llm_service(
    provider_type: Optional[str] = None,
    config: Optional[LLMConfig] = None,
) -> LLMService:
    """
    Get LLM service instance.

    Args:
        provider_type: Provider type override
        config: Settings chosen on the settings screen; .env when omitted

    Returns:
        LLMService instance
    """
    return LLMService(provider_type=provider_type, config=config)
