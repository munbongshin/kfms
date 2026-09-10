"""
LLM Provider Factory.
Creates appropriate LLM provider instance based on configuration.
"""
from typing import Optional

from app.llm.base import BaseLLMProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.groq_provider import GroqProvider
from app.config import settings


def create_provider(provider_type: Optional[str] = None) -> BaseLLMProvider:
    """
    Create LLM provider instance based on configuration.

    Args:
        provider_type: Provider type override ('ollama' or 'groq')
                      If None, uses settings.LLM_PROVIDER

    Returns:
        BaseLLMProvider instance

    Raises:
        ValueError: If provider type is unknown or configuration is missing
    """
    # Use provided type or default from settings
    prov_type = (provider_type or settings.LLM_PROVIDER).lower()

    if prov_type == "ollama":
        return OllamaProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            timeout=settings.OLLAMA_TIMEOUT
        )

    elif prov_type == "groq":
        if not settings.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY is not configured. "
                "Add it to .env file or use Ollama instead."
            )

        return GroqProvider(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            timeout=settings.GROQ_TIMEOUT
        )

    else:
        raise ValueError(
            f"Unknown LLM provider: {prov_type}. "
            f"Supported providers: 'ollama', 'groq'"
        )


async def get_active_provider() -> BaseLLMProvider:
    """
    Get the currently configured LLM provider.

    Returns:
        Active LLM provider instance
    """
    return create_provider()


async def test_provider(provider_type: Optional[str] = None) -> dict:
    """
    Test LLM provider connection.

    Args:
        provider_type: Provider type to test

    Returns:
        Dict with test results
    """
    try:
        provider = create_provider(provider_type)
        is_available = await provider.validate_connection()

        return {
            "provider": provider_type or settings.LLM_PROVIDER,
            "model": provider.model,
            "status": "available" if is_available else "unavailable",
            "error": None
        }
    except Exception as e:
        return {
            "provider": provider_type or settings.LLM_PROVIDER,
            "model": None,
            "status": "error",
            "error": str(e)
        }
