"""The effective LLM configuration: saved settings over .env and defaults.

Stored shape: {"provider": name, "profiles": {name: {base_url, model, api_key}}}
— one profile per serving platform, so switching platforms loses nothing.

Kept free of database and HTTP code so the rules — what overrides what, how
keys stay secret — can be tested on their own.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from app.llm.platforms import PLATFORMS, Platform, get_platform

EDITABLE = ("base_url", "model")


@dataclass
class Profile:
    base_url: str
    model: str
    api_key: str


@dataclass
class LLMConfig:
    provider: str
    profiles: Dict[str, Profile]
    # "saved" once anything was saved from the settings screen, else "env".
    source: str

    @property
    def platform(self) -> Platform:
        return get_platform(self.provider)

    @property
    def active(self) -> Profile:
        return self.profiles[self.provider]


def _env_defaults(env: Any) -> Dict[str, Dict[str, str]]:
    """The only platforms .env knows about are Ollama and Groq."""
    return {
        "ollama": {"base_url": env.OLLAMA_BASE_URL, "model": env.OLLAMA_MODEL},
        "groq": {"model": env.GROQ_MODEL, "api_key": env.GROQ_API_KEY},
    }


def _clean(value: Optional[str]) -> str:
    return value.strip() if isinstance(value, str) else ""


def resolve(saved: Optional[Mapping[str, Any]], env: Any) -> LLMConfig:
    """Saved values win; a field never saved falls back to .env, then the default."""
    saved_profiles = (saved or {}).get("profiles") or {}
    defaults = _env_defaults(env)

    profiles: Dict[str, Profile] = {}
    for p in PLATFORMS:
        mine = saved_profiles.get(p.name) or {}
        env_p = defaults.get(p.name, {})

        def pick(field: str, fallback: str = "") -> str:
            return _clean(mine.get(field)) or _clean(env_p.get(field)) or fallback

        base_url = p.default_base_url if p.fixed_base_url else pick("base_url", p.default_base_url)
        profiles[p.name] = Profile(
            base_url=base_url.rstrip("/"),
            model=pick("model"),
            api_key=pick("api_key") if p.api_key != "none" else "",
        )

    provider = _clean((saved or {}).get("provider")).lower()
    if not get_platform(provider):
        provider = _clean(env.LLM_PROVIDER).lower()
    if not get_platform(provider):
        provider = PLATFORMS[0].name

    return LLMConfig(provider=provider, profiles=profiles, source="saved" if saved else "env")


def apply_update(stored: Optional[Mapping[str, Any]], update: Mapping[str, Any]) -> Dict[str, Any]:
    """The settings to store after a save.

    A blank key means "leave it as it is" — the browser never holds a stored
    key, so the field is blank unless the user typed a new one. Clearing a key
    takes an explicit `clear_api_key`.
    """
    profiles: Dict[str, Dict[str, Any]] = {
        name: dict(values) for name, values in ((stored or {}).get("profiles") or {}).items()
    }

    for name, changes in (update.get("profiles") or {}).items():
        platform = get_platform(name)
        if not platform:
            continue
        profile = profiles.setdefault(name, {})

        for field in EDITABLE:
            if changes.get(field) is not None:
                profile[field] = _clean(changes[field])

        if platform.api_key == "none":
            profile.pop("api_key", None)
            continue
        key = _clean(changes.get("api_key"))
        if key:
            profile["api_key"] = key
        if changes.get("clear_api_key"):
            profile.pop("api_key", None)

    provider = _clean(update.get("provider")) or (stored or {}).get("provider")
    return {"provider": provider, "profiles": profiles}


def validate(cfg: LLMConfig) -> List[str]:
    """Problems that would stop the chosen platform from working."""
    platform, profile = cfg.platform, cfg.active
    errors: List[str] = []
    if not profile.base_url.startswith(("http://", "https://")):
        errors.append(f"{platform.label} 서버 주소는 http:// 또는 https://로 시작해야 합니다")
    if not profile.model:
        errors.append(f"{platform.label} 모델을 선택하세요")
    if platform.api_key == "required" and not profile.api_key:
        errors.append(f"{platform.label} API 키를 입력하세요")
    return errors


def _hint(key: str) -> Optional[str]:
    return f"••••{key[-4:]}" if key else None


def public_view(cfg: LLMConfig) -> Dict[str, Any]:
    """What the browser may see: every platform's settings but never a key."""
    return {
        "provider": cfg.provider,
        "source": cfg.source,
        "platforms": [
            {
                "name": p.name,
                "label": p.label,
                "protocol": p.protocol,
                "description": p.description,
                "hint": p.hint,
                "api_key": p.api_key,
                "fixed_base_url": p.fixed_base_url,
                "external": p.external,
                "default_base_url": p.default_base_url,
                "base_url": cfg.profiles[p.name].base_url,
                "model": cfg.profiles[p.name].model,
                "api_key_set": bool(cfg.profiles[p.name].api_key),
                "api_key_hint": _hint(cfg.profiles[p.name].api_key),
            }
            for p in PLATFORMS
        ],
    }
