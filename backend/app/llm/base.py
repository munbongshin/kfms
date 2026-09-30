"""
Base LLM Provider interface.
Defines the contract for all LLM provider implementations.
"""
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


# Shared by every provider so the rules cannot drift apart between them.
SQL_RULES = """RULES:
1. Use ONLY SELECT statements (read-only mode enforced)
2. Include LIMIT 1000 if no limit specified
3. Use table/column names exactly as shown in schema
4. Return ONLY the SQL query, no explanations
5. Use proper PostgreSQL syntax (ILIKE, ::, etc.)
6. Give every computed column (aggregates, arithmetic, CASE, etc.) a short
   Korean alias in double quotes, e.g. SUM(total_amount) AS "매출액 합계",
   COUNT(*) AS "건수", AVG(price) AS "평균 단가". Results are read by Korean
   users, so never leave PostgreSQL's default names such as sum or count.
   Plain columns keep their real names; the screen labels them itself."""


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
        # Platform name recorded in query history; subclasses override.
        self.name = self.__class__.__name__.replace("Provider", "").lower()
        self.config = kwargs

    @abstractmethod
    async def generate_sql(
        self,
        question: str,
        schema: Dict[str, List[Dict[str, Any]]],
        context: str = "",
        table_comments: Optional[Dict[str, str]] = None,
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

    def format_schema_context(
        self,
        schema: Dict[str, List[Dict[str, Any]]],
        table_comments: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Format database schema into a readable string for prompts.

        Args:
            schema: Database schema (table name -> columns)
            table_comments: Table descriptions (COMMENT ON TABLE), by table name

        Returns:
            Formatted schema as string
        """
        if not schema:
            return "No schema information available."

        schema_lines = []
        for table_name, columns in schema.items():
            # The table's description lets "승인내역" in a question find v_approval.
            described = (table_comments or {}).get(table_name)
            schema_lines.append(f"\nTable: {table_name}" + (f" -- {described}" if described else ""))
            schema_lines.append("Columns:")
            for col in columns:
                nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
                default = f" DEFAULT {col.get('default')}" if col.get('default') else ""
                # The business name lets a Korean question ("카드번호별")
                # find its column. The display name wins so workbook notation
                # users never say (현지금액) does not end up in aliases.
                name = col.get("label") or col.get("comment")
                label = f" -- {name}" if name else ""
                schema_lines.append(
                    f"  - {col['name']} ({col['type']}) {nullable}{default}{label}"
                )

        return "\n".join(schema_lines)

    @staticmethod
    def strip_reasoning(response: str) -> str:
        """Drop a reasoning model's <think>…</think> preamble (qwen3, deepseek-r1)."""
        return re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL | re.IGNORECASE)

    def extract_sql_from_response(self, response: str) -> str:
        """
        Extract SQL query from LLM response.
        Handles cases where LLM wraps SQL in markdown code blocks.

        Args:
            response: Raw LLM response

        Returns:
            Extracted SQL query
        """
        response = BaseLLMProvider.strip_reasoning(response)

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
