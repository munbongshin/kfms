"""
LLM Provider Factory.
Creates the provider for the serving platform chosen on the settings screen.
"""
from typing import Optional

from app.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_compatible_provider import OpenAICompatibleProvider
from app.llm.platforms import get_platform
from app.llm.settings_resolver import LLMConfig, resolve


def create_provider(
    provider_type: Optional[str] = None,
    config: Optional[LLMConfig] = None,
) -> BaseLLMProvider:
    """
    Create the LLM provider for a serving platform.

    Args:
        provider_type: Platform override (ollama, lmstudio, vllm, openai_compatible, groq);
                      the configured platform when None
        config: Settings chosen on the settings screen; .env when omitted

    Raises:
        ValueError: If the platform is unknown or its settings are incomplete
    """
    cfg = config or resolve(None, settings)
    name = (provider_type or cfg.provider).lower()
    platform = get_platform(name)
    if not platform:
        raise ValueError(f"지원하지 않는 LLM 플랫폼입니다: {name}")

    profile = cfg.profiles[name]
    if platform.api_key == "required" and not profile.api_key:
        raise ValueError(
            f"{platform.label} API 키가 설정되지 않았습니다. 설정 화면에서 입력하세요."
        )

    if platform.protocol == "ollama":
        return OllamaProvider(
            base_url=profile.base_url,
            model=profile.model,
            timeout=settings.OLLAMA_TIMEOUT
        )

    return OpenAICompatibleProvider(
        base_url=profile.base_url,
        model=profile.model,
        api_key=profile.api_key or None,
        # Local models can take minutes on modest hardware; hosted APIs cannot.
        timeout=settings.GROQ_TIMEOUT if platform.cloud else settings.OLLAMA_TIMEOUT,
        name=platform.name,
    )
