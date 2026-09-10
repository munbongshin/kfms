"""
Groq LLM Provider implementation.
Uses official Groq SDK for cloud-based inference.
"""
from typing import Dict, List, Any
from groq import AsyncGroq

from app.llm.base import BaseLLMProvider


class GroqProvider(BaseLLMProvider):
    """
    Groq provider for blazing-fast cloud LLM inference.
    Requires GROQ_API_KEY.
    """

    def __init__(self, api_key: str, model: str, timeout: int = 60):
        """
        Initialize Groq provider.

        Args:
            api_key: Groq API key
            model: Model name (e.g., mixtral-8x7b-32768, llama3-70b-8192)
            timeout: Request timeout in seconds
        """
        super().__init__(model)
        self.client = AsyncGroq(api_key=api_key, timeout=timeout)

    async def generate_sql(
        self,
        question: str,
        schema: Dict[str, List[Dict[str, Any]]],
        context: str = ""
    ) -> str:
        """
        Generate SQL query using Groq.

        Args:
            question: User's natural language question
            schema: Database schema
            context: Optional context

        Returns:
            Generated SQL query
        """
        # Build prompt
        schema_context = self.format_schema_context(schema)

        system_prompt = f"""You are a PostgreSQL expert. Generate SQL queries based on natural language questions.

DATABASE SCHEMA:
{schema_context}

RULES:
1. Use ONLY SELECT statements (read-only mode enforced)
2. Include LIMIT 1000 if no limit specified
3. Use table/column names exactly as shown in schema
4. Return ONLY the SQL query, no explanations
5. Use proper PostgreSQL syntax (ILIKE, ::, etc.)"""

        context_part = f"CONTEXT: {context}\n\n" if context else ""
        user_prompt = f"""{context_part}QUESTION: {question}

SQL:"""

        # Call Groq API
        chat_completion = await self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            model=self.model,
            temperature=0.1,  # Low temperature for deterministic code generation
            max_tokens=1024,
            top_p=0.9,
        )

        sql_response = chat_completion.choices[0].message.content or ""

        # Extract clean SQL
        sql = self.extract_sql_from_response(sql_response)

        return sql

    async def recommend_visualization(
        self,
        sql: str,
        result_sample: List[Dict[str, Any]],
        max_rows: int = 10
    ) -> Dict[str, Any]:
        """
        Recommend visualization type using Groq.

        Args:
            sql: SQL query
            result_sample: Sample results
            max_rows: Max rows to analyze

        Returns:
            Visualization recommendation
        """
        # Sample first N rows
        sample = result_sample[:max_rows]

        system_prompt = """You are a data visualization expert. Recommend the best chart type for given SQL query results.

Available chart types: table, bar, line, pie

Respond ONLY in valid JSON format:
{
  "chart_type": "bar",
  "x_axis": "column_name",
  "y_axis": "column_name",
  "reasoning": "Brief explanation"
}"""

        user_prompt = f"""SQL: {sql}

SAMPLE DATA (first {len(sample)} rows):
{sample}

Recommendation:"""

        # Call Groq API
        chat_completion = await self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            model=self.model,
            temperature=0.3,
            max_tokens=512,
        )

        viz_response = chat_completion.choices[0].message.content or ""

        # Parse JSON response
        import json
        try:
            # Extract JSON if wrapped in markdown
            if "```json" in viz_response.lower():
                json_part = viz_response.split("```json")[1].split("```")[0]
                viz_data = json.loads(json_part.strip())
            elif "```" in viz_response:
                json_part = viz_response.split("```")[1].split("```")[0]
                viz_data = json.loads(json_part.strip())
            else:
                viz_data = json.loads(viz_response.strip())

            return viz_data
        except (json.JSONDecodeError, IndexError):
            # Fallback to table if JSON parsing fails
            return {
                "chart_type": "table",
                "x_axis": None,
                "y_axis": None,
                "reasoning": "Unable to parse recommendation, defaulting to table"
            }

    async def validate_connection(self) -> bool:
        """
        Check if Groq API is accessible.

        Returns:
            True if Groq is available
        """
        try:
            # Simple test request
            await self.client.chat.completions.create(
                messages=[{"role": "user", "content": "test"}],
                model=self.model,
                max_tokens=1,
            )
            return True
        except Exception:
            return False
