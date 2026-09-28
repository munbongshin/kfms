"""
LLM settings API.
Choose the serving platform (Ollama, LM Studio, vLLM, other OpenAI-compatible
servers, Groq) that turns questions into SQL, and check that it answers.
"""
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.db.repositories.llm_settings import LLMSettingsRepository
from app.llm.factory import create_provider
from app.llm.openai_compatible_provider import OpenAICompatibleProvider
from app.llm.settings_resolver import LLMConfig, apply_update, public_view, resolve, validate

router = APIRouter(prefix="/llm-settings", tags=["LLM Settings"])


class ProfileUpdate(BaseModel):
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = Field(None, description="New key; blank keeps the stored key")
    clear_api_key: bool = False


class LLMSettingsUpdate(BaseModel):
    """What the settings screen sends: the chosen platform and edited profiles."""
    provider: str
    profiles: Dict[str, ProfileUpdate] = {}


async def current_llm_config(db: AsyncSession = Depends(get_db)) -> LLMConfig:
    """The LLM configuration in effect: saved settings over .env."""
    saved = await LLMSettingsRepository(db).load()
    return resolve(saved, settings)


async def _proposed(update: LLMSettingsUpdate, repo: LLMSettingsRepository) -> tuple:
    """The settings a save would store, and the configuration they produce."""
    values = apply_update(await repo.load(), update.model_dump())
    return values, resolve(values, settings)


async def _ollama_models(base_url: str) -> List[str]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{base_url.rstrip('/')}/api/tags")
        response.raise_for_status()
        return sorted(m["name"] for m in response.json().get("models", []))


async def _list_models(config: LLMConfig) -> List[str]:
    profile = config.active
    if config.platform.protocol == "ollama":
        return await _ollama_models(profile.base_url)
    return await OpenAICompatibleProvider(
        base_url=profile.base_url, model=profile.model, api_key=profile.api_key or None
    ).list_models()


@router.get("")
async def get_llm_settings(config: LLMConfig = Depends(current_llm_config)) -> Dict[str, Any]:
    return public_view(config)


@router.put("")
async def save_llm_settings(update: LLMSettingsUpdate, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Save the choice. It applies from the next question; no restart needed."""
    repo = LLMSettingsRepository(db)
    values, config = await _proposed(update, repo)

    errors = validate(config)
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=" · ".join(errors))

    await repo.save(values)
    return public_view(config)


@router.post("/models")
async def list_models(update: LLMSettingsUpdate, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """The models the chosen platform's server offers, for the model picker.

    Takes the form as it stands, so an address typed but not yet saved works;
    a blank key uses the stored one.
    """
    _, config = await _proposed(update, LLMSettingsRepository(db))
    if not config.active.base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="http:// 주소를 입력하세요")
    try:
        return {"models": await _list_models(config)}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{config.platform.label} 서버에서 모델 목록을 받지 못했습니다: {exc}",
        )


@router.post("/test")
async def test_llm_settings(update: LLMSettingsUpdate, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Check the settings on the form — saved or not — against the real server."""
    _, config = await _proposed(update, LLMSettingsRepository(db))
    label, model = config.platform.label, config.active.model

    errors = validate(config)
    if errors:
        return {"ok": False, "message": " · ".join(errors)}

    started = time.perf_counter()

    def elapsed() -> int:
        return int((time.perf_counter() - started) * 1000)

    try:
        models = await _list_models(config)
    except Exception as exc:
        if config.platform.protocol == "ollama":
            return {"ok": False, "message": f"{label}에 연결하지 못했습니다: {exc}"}
        # Some servers (TGI, older llama.cpp) have no model list; ask for one token instead.
        try:
            provider = create_provider(config=config)
            await provider._chat([{"role": "user", "content": "ping"}], temperature=0, max_tokens=1)
            return {"ok": True, "message": f"{label} 연결 성공 · {model} (모델 목록 미지원 서버)", "elapsed_ms": elapsed()}
        except Exception as chat_exc:
            return {"ok": False, "message": f"{label}에 연결하지 못했습니다: {chat_exc}"}

    # Reaching the server is not enough: the chosen model must be available there.
    if models and model not in models:
        return {
            "ok": False,
            "message": f"서버에는 연결되지만 '{model}' 모델이 없습니다 — 목록에서 고르세요",
            "models": models,
            "elapsed_ms": elapsed(),
        }
    return {"ok": True, "message": f"{label} 연결 성공 · {model}", "models": models, "elapsed_ms": elapsed()}
