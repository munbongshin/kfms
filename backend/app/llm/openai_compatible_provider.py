"""
OpenAI-compatible LLM provider.
One client for every server that speaks /v1/chat/completions: LM Studio,
vLLM, llama.cpp, LocalAI, SGLang, TGI, Groq, OpenAI.
"""
import json
from typing import Any, Dict, List, Optional

import httpx

from app.llm.base import BaseLLMProvider, SQL_RULES


def model_ids(body: Dict[str, Any]) -> List[str]:
    """Model names from a GET /v1/models response."""
    return sorted(m["id"] for m in body.get("data") or [] if m.get("id"))


def message_text(body: Dict[str, Any]) -> str:
    """The assistant's answer from a chat-completions response."""
    return body["choices"][0]["message"].get("content") or ""


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
        timeout: int = 120,
        name: str = "openai_compatible",
    ):
        """
        Args:
            base_url: Server address ending in /v1, e.g. http://localhost:1234/v1
            model: Model id as the server lists it
            api_key: Bearer token, if the server requires one
            timeout: Request timeout in seconds
            name: Platform name recorded in query history (lmstudio, vllm, groq...)
        """
        super().__init__(model)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.name = name
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def _chat(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                },
            )
            if response.is_error:
                # The server's own message (e.g. "model not loaded") is the useful part.
                raise RuntimeError(f"{response.status_code} {response.text[:300]}")
            return message_text(response.json())

    async def list_models(self) -> List[str]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}/models", headers=self.headers)
            response.raise_for_status()
            return model_ids(response.json())

    async def generate_sql(
        self,
        question: str,
        schema: Dict[str, List[Dict[str, Any]]],
        context: str = ""
    ) -> str:
        schema_context = self.format_schema_context(schema)

        system_prompt = f"""You are a PostgreSQL expert. Generate SQL queries based on natural language questions.

DATABASE SCHEMA:
{schema_context}

{SQL_RULES}"""

        context_part = f"CONTEXT: {context}\n\n" if context else ""
        user_prompt = f"""{context_part}QUESTION: {question}

SQL:"""

        answer = await self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # Low temperature for deterministic code generation
            # Reasoning models spend tokens thinking before the SQL.
            max_tokens=2048,
        )
        return self.extract_sql_from_response(answer)

    async def recommend_visualization(
        self,
        sql: str,
        result_sample: List[Dict[str, Any]],
        max_rows: int = 10
    ) -> Dict[str, Any]:
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

        answer = await self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=512,
        )

        try:
            text = self.strip_reasoning(answer)
            if "```" in text:
                text = text.split("```")[1].removeprefix("json")
            return json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            return {
                "chart_type": "table",
                "x_axis": None,
                "y_axis": None,
                "reasoning": "Unable to parse recommendation, defaulting to table"
            }

    async def validate_connection(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception:
            return False
