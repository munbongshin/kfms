"""
Base LLM Provider interface.
Defines the contract for all LLM provider implementations.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    All providers (Ollama, Groq, etc.) must implement these methods.
    """

    def __init__(self, model: str, **kwargs):
        """
        Initialize LLM provider.

        Args:
            model: Model name/identifier
            **kwargs: Provider-specific configuration
        """
        self.model = model
        self.config = kwargs

    @abstractmethod
    async def generate_sql(
        self,
        question: str,
        schema: Dict[str, List[Dict[str, Any]]],
        context: str = ""
    ) -> str:
        """
        Generate SQL query from natural language question.

        Args:
            question: User's natural language question
            schema: Database schema (table name -> columns)
            context: Optional context (previous queries, hints)

        Returns:
            Generated SQL query as string

        Raises:
            Exception: If generation fails
        """
        pass

    @abstractmethod
    async def recommend_visualization(
        self,
        sql: str,
        result_sample: List[Dict[str, Any]],
        max_rows: int = 10
    ) -> Dict[str, Any]:
        """
        Recommend visualization type based on query and results.

        Args:
            sql: SQL query that was executed
            result_sample: Sample of query results
            max_rows: Maximum rows to consider

        Returns:
            Dict with visualization recommendation:
            {
                "chart_type": "bar" | "line" | "pie" | "table",
                "x_axis": "column_name",
                "y_axis": "column_name",
                "reasoning": "Explanation of recommendation"
            }

        Raises:
            Exception: If recommendation fails
        """
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        Check if LLM provider is reachable and configured correctly.

        Returns:
            True if provider is available, False otherwise
        """
        pass

    def format_schema_context(self, schema: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Format database schema into a readable string for prompts.

        Args:
            schema: Database schema (table name -> columns)

        Returns:
            Formatted schema as string
        """
        if not schema:
            return "No schema information available."

        schema_lines = []
        for table_name, columns in schema.items():
            schema_lines.append(f"\nTable: {table_name}")
            schema_lines.append("Columns:")
            for col in columns:
                nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
                default = f" DEFAULT {col.get('default')}" if col.get('default') else ""
                schema_lines.append(
                    f"  - {col['name']} ({col['type']}) {nullable}{default}"
                )

        return "\n".join(schema_lines)

    def extract_sql_from_response(self, response: str) -> str:
        """
        Extract SQL query from LLM response.
        Handles cases where LLM wraps SQL in markdown code blocks.

        Args:
            response: Raw LLM response

        Returns:
            Extracted SQL query
        """
        # Remove markdown SQL code blocks if present
        if "```sql" in response.lower():
            # Extract content between ```sql and ```
            parts = response.split("```sql")
            if len(parts) > 1:
                sql_part = parts[1].split("```")[0]
                return sql_part.strip()

        if "```" in response:
            # Extract content between ``` and ```
            parts = response.split("```")
            if len(parts) >= 3:
                return parts[1].strip()

        # Return cleaned response
        return response.strip()
