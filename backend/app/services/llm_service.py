"""
LLM Service for orchestrating LLM provider calls.
Handles SQL generation and visualization recommendations.
"""
from typing import Dict, List, Any, Optional

from app.llm.factory import create_provider
from app.llm.base import BaseLLMProvider
from app.db.connection_pool import DatabaseConnectionPool


class LLMService:
    """
    Service for managing LLM operations.
    """

    def __init__(self, provider_type: Optional[str] = None):
        """
        Initialize LLM service.

        Args:
            provider_type: LLM provider type ('ollama' or 'groq')
                          If None, uses default from settings
        """
        self.provider: BaseLLMProvider = create_provider(provider_type)

    async def generate_sql(
        self,
        question: str,
        connection_pool: DatabaseConnectionPool,
        database_id: str,
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language question.

        Args:
            question: User's natural language question
            connection_pool: Database connection pool
            database_id: Database connection ID
            context: Optional context (previous queries, hints)

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

        # Generate SQL using LLM
        try:
            sql = await self.provider.generate_sql(
                question=question,
                schema=schema,
                context=context
            )

            return {
                "sql": sql,
                "provider": self.provider.__class__.__name__.replace('Provider', '').lower(),
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


def get_llm_service(provider_type: Optional[str] = None) -> LLMService:
    """
    Get LLM service instance.

    Args:
        provider_type: Provider type override

    Returns:
        LLMService instance
    """
    return LLMService(provider_type=provider_type)
