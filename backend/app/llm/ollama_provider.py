"""
Ollama LLM Provider implementation.
Connects to local Ollama server via HTTP API.
"""
from typing import Dict, List, Any
import httpx

from app.llm.base import BaseLLMProvider, SQL_RULES


class OllamaProvider(BaseLLMProvider):
    """
    Ollama provider for local LLM inference.
    Communicates with Ollama server running on localhost.
    """

    def __init__(self, base_url: str, model: str, timeout: int = 120):
        """
        Initialize Ollama provider.

        Args:
            base_url: Ollama server URL (e.g., http://localhost:11434)
            model: Model name (e.g., llama3.1, codellama, mixtral)
            timeout: Request timeout in seconds
        """
        super().__init__(model)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.generate_endpoint = f"{self.base_url}/api/generate"
        self.tags_endpoint = f"{self.base_url}/api/tags"

    async def generate_sql(
        self,
        question: str,
        schema: Dict[str, List[Dict[str, Any]]],
        context: str = ""
    ) -> str:
        """
        Generate SQL query using Ollama.

        Args:
            question: User's natural language question
            schema: Database schema
            context: Optional context

        Returns:
            Generated SQL query
        """
        # Build prompt
        schema_context = self.format_schema_context(schema)

        prompt = f"""You are a PostgreSQL expert. Generate SQL queries based on natural language questions.

DATABASE SCHEMA:
{schema_context}

{SQL_RULES}

{f"CONTEXT: {context}" if context else ""}

QUESTION: {question}

SQL:"""

        # Call Ollama API
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.generate_endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for deterministic code generation
                        "top_p": 0.9,
                    }
                }
            )
            response.raise_for_status()

        data = response.json()
        sql_response = data.get("response", "")

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
        Recommend visualization type using Ollama.

        Args:
            sql: SQL query
            result_sample: Sample results
            max_rows: Max rows to analyze

        Returns:
            Visualization recommendation
        """
        # Sample first N rows
        sample = result_sample[:max_rows]

        prompt = f"""Given this SQL query and sample results, recommend the best chart type.

SQL: {sql}

SAMPLE DATA (first {len(sample)} rows):
{sample}

Available chart types: table, bar, line, pie

Respond in JSON format:
{{
  "chart_type": "bar",
  "x_axis": "column_name",
  "y_axis": "column_name",
  "reasoning": "Brief explanation"
}}

JSON:"""

        # Call Ollama API
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.generate_endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                    }
                }
            )
            response.raise_for_status()

        data = response.json()
        viz_response = data.get("response", "")

        # Try to parse JSON response
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
        Check if Ollama server is reachable.

        Returns:
            True if Ollama is available
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(self.tags_endpoint)
                response.raise_for_status()
                return True
        except Exception:
            return False
