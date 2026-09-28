"""Which LLM answers questions, and how that choice is stored.

Each serving platform (Ollama, LM Studio, vLLM, other OpenAI-compatible
servers, Groq) keeps its own address, model and key, so switching between them
loses nothing. Saved settings override .env; anything never saved falls back
to .env or the platform's default. API keys are never sent back to the browser,
and a save that leaves a key blank must not erase the stored one.
"""
from types import SimpleNamespace

import pytest

from app.llm.platforms import PLATFORMS, get_platform
from app.llm.settings_resolver import apply_update, public_view, resolve, validate

ENV = SimpleNamespace(
    LLM_PROVIDER="ollama",
    OLLAMA_BASE_URL="http://10.1.10.238:11434",
    OLLAMA_MODEL="gemma4:31b",
    GROQ_MODEL="openai/gpt-oss-120b",
    GROQ_API_KEY="gsk_env_key_1234",
)


def saved(provider="ollama", **profiles):
    return {"provider": provider, "profiles": profiles}


# --- platforms -------------------------------------------------------------

def test_the_serving_platforms_on_offer():
    names = [p.name for p in PLATFORMS]
    assert names == ["ollama", "lmstudio", "vllm", "openai_compatible", "groq"]


def test_every_openai_style_platform_shares_one_protocol():
    for name in ("lmstudio", "vllm", "openai_compatible", "groq"):
        assert get_platform(name).protocol == "openai"


def test_vllm_does_not_default_to_the_kfms_port():
    # vLLM listens on 8000 by default, which is where the KFMS API runs.
    assert ":8000" not in get_platform("vllm").default_base_url


def test_groq_is_the_only_one_that_leaves_the_network():
    assert [p.name for p in PLATFORMS if p.external] == ["groq"]


# --- resolve ---------------------------------------------------------------

def test_nothing_saved_means_env_and_platform_defaults():
    cfg = resolve(None, ENV)
    assert cfg.provider == "ollama"
    assert cfg.source == "env"
    assert cfg.profiles["ollama"].model == "gemma4:31b"
    assert cfg.profiles["lmstudio"].base_url == "http://localhost:1234/v1"
    assert cfg.profiles["groq"].api_key == "gsk_env_key_1234"


def test_saved_settings_override_env():
    cfg = resolve(saved("lmstudio", lmstudio={"model": "qwen2.5-coder-14b"}), ENV)
    assert cfg.provider == "lmstudio"
    assert cfg.active.model == "qwen2.5-coder-14b"
    assert cfg.source == "saved"


def test_each_platform_keeps_its_own_settings():
    cfg = resolve(saved(
        "vllm",
        lmstudio={"base_url": "http://pc1:1234/v1", "model": "a"},
        vllm={"base_url": "http://gpu:8001/v1", "model": "b"},
    ), ENV)
    assert cfg.profiles["lmstudio"].model == "a"
    assert cfg.profiles["vllm"].model == "b"


def test_an_unsaved_field_still_comes_from_env():
    cfg = resolve(saved("groq", groq={"model": "llama-3.3-70b-versatile"}), ENV)
    assert cfg.active.api_key == "gsk_env_key_1234"


def test_groq_always_uses_its_own_address():
    cfg = resolve(saved("groq", groq={"base_url": "http://evil.example/v1"}), ENV)
    assert cfg.active.base_url == "https://api.groq.com/openai/v1"


def test_an_unknown_saved_provider_falls_back_to_env():
    assert resolve(saved("nonexistent"), ENV).provider == "ollama"


def test_a_trailing_slash_is_dropped():
    cfg = resolve(saved("vllm", vllm={"base_url": "http://gpu:8001/v1/"}), ENV)
    assert cfg.active.base_url == "http://gpu:8001/v1"


# --- apply_update ----------------------------------------------------------

def test_saving_one_platform_leaves_the_others():
    stored = saved("lmstudio", lmstudio={"model": "a"})
    after = apply_update(stored, {"provider": "vllm", "profiles": {"vllm": {"model": "b"}}})
    assert after["provider"] == "vllm"
    assert after["profiles"]["lmstudio"]["model"] == "a"
    assert after["profiles"]["vllm"]["model"] == "b"


def test_a_blank_key_keeps_the_stored_key():
    stored = saved("vllm", vllm={"api_key": "sk-old"})
    after = apply_update(stored, {"provider": "vllm", "profiles": {"vllm": {"api_key": ""}}})
    assert after["profiles"]["vllm"]["api_key"] == "sk-old"


def test_a_new_key_replaces_the_stored_one():
    stored = saved("vllm", vllm={"api_key": "sk-old"})
    after = apply_update(stored, {"provider": "vllm", "profiles": {"vllm": {"api_key": "sk-new"}}})
    assert after["profiles"]["vllm"]["api_key"] == "sk-new"


def test_a_key_can_be_cleared_on_purpose():
    stored = saved("vllm", vllm={"api_key": "sk-old"})
    after = apply_update(stored, {"provider": "vllm", "profiles": {"vllm": {"clear_api_key": True}}})
    assert after["profiles"]["vllm"].get("api_key") is None


def test_a_platform_without_keys_never_stores_one():
    after = apply_update(None, {"provider": "ollama", "profiles": {"ollama": {"api_key": "x"}}})
    assert "api_key" not in after["profiles"]["ollama"]


def test_unknown_platforms_are_ignored():
    after = apply_update(None, {"provider": "ollama", "profiles": {"bogus": {"model": "x"}}})
    assert "bogus" not in after["profiles"]


def test_spaces_are_trimmed():
    after = apply_update(None, {"provider": "ollama", "profiles": {"ollama": {"model": "  m  "}}})
    assert after["profiles"]["ollama"]["model"] == "m"


# --- public_view -----------------------------------------------------------

def test_the_browser_never_sees_a_key():
    cfg = resolve(saved("vllm", vllm={"api_key": "sk-secret-9999"}), ENV)
    view = public_view(cfg)
    assert "sk-secret-9999" not in str(view)
    assert "gsk_env_key_1234" not in str(view)
    vllm = next(p for p in view["platforms"] if p["name"] == "vllm")
    assert vllm["api_key_set"] is True
    assert vllm["api_key_hint"] == "••••9999"


def test_the_view_describes_every_platform():
    view = public_view(resolve(None, ENV))
    assert [p["name"] for p in view["platforms"]] == [p.name for p in PLATFORMS]
    groq = next(p for p in view["platforms"] if p["name"] == "groq")
    assert groq["api_key"] == "required"
    assert groq["fixed_base_url"] is True


# --- validate --------------------------------------------------------------

def test_a_complete_setting_is_valid():
    cfg = resolve(saved("lmstudio", lmstudio={"model": "qwen"}), ENV)
    assert validate(cfg) == []


@pytest.mark.parametrize("url", ["", "localhost:1234/v1", "ftp://x"])
def test_the_address_must_be_http(url):
    cfg = resolve(saved("openai_compatible", openai_compatible={"base_url": url, "model": "m"}), ENV)
    assert validate(cfg)


def test_a_model_is_required():
    cfg = resolve(saved("vllm", vllm={"model": ""}), ENV)
    assert validate(cfg)


def test_groq_needs_a_key():
    env = SimpleNamespace(**{**vars(ENV), "GROQ_API_KEY": ""})
    assert validate(resolve(saved("groq", groq={"model": "m"}), env))


def test_local_servers_run_without_a_key():
    cfg = resolve(saved("vllm", vllm={"model": "m"}), ENV)
    assert validate(cfg) == []


def test_only_the_chosen_platform_is_checked():
    # An unfinished vLLM entry must not block saving Ollama.
    cfg = resolve(saved("ollama", vllm={"base_url": "nonsense"}), ENV)
    assert validate(cfg) == []
