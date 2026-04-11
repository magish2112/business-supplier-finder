"""
Единые настройки текстовой модели (любой провайдер через переменные окружения).

Провайдер: LLM_PROVIDER
  - anthropic     — Claude (пакет anthropic)
  - openai        — OpenAI API (пакет openai)
  - openai_compatible — любой OpenAI-совместимый endpoint (Perplexity, vLLM, LiteLLM proxy и т.д.)
  - ollama        — локальный Ollama (HTTP)
  - none          — без вызовов модели, complete_json вернёт "{}"
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# Сырые значения LLM_PROVIDER → нормализованный провайдер
_PROVIDER_ALIASES = {
    "claude": "anthropic",
    "anthropic_claude": "anthropic",
    "perplexity": "openai_compatible",
    "groq": "openai_compatible",
    "litellm": "openai_compatible",
    "vllm": "openai_compatible",
}


def _env_bool(key: str, default: str = "false") -> bool:
    return os.getenv(key, default).lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class LLMSettings:
    """Текущий профиль LLM (читается при каждом вызове load_llm_settings — можно менять .env без рестарта)."""

    provider: str
    # Anthropic
    anthropic_api_key: str
    anthropic_model: str
    # OpenAI / совместимые
    openai_api_key: str
    openai_base_url: Optional[str]
    openai_model: str
    # Ollama
    ollama_host: str
    ollama_model: str
    # Общее
    max_tokens_default: int
    request_timeout_sec: int
    log_requests: bool

    @property
    def provider_normalized(self) -> str:
        p = (self.provider or "none").strip().lower()
        if p in ("", "disabled", "off"):
            return "none"
        return p


def load_llm_settings() -> LLMSettings:
    raw_provider = os.getenv("LLM_PROVIDER", "none").strip().lower()
    provider = _PROVIDER_ALIASES.get(raw_provider, raw_provider)

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_key:
        openai_key = os.getenv("PERPLEXITY_API_KEY", "").strip()

    openai_base = os.getenv("OPENAI_BASE_URL", "").strip() or None
    if provider == "openai_compatible" and not openai_base:
        if raw_provider == "perplexity" or (
            openai_key and openai_key == os.getenv("PERPLEXITY_API_KEY", "").strip()
        ):
            openai_base = "https://api.perplexity.ai"

    openai_model = os.getenv("OPENAI_MODEL", "").strip()
    if not openai_model and raw_provider == "perplexity":
        openai_model = os.getenv("PERPLEXITY_MODEL", "sonar-pro").strip()
    if not openai_model:
        openai_model = "gpt-4o-mini"

    return LLMSettings(
        provider=provider,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022").strip(),
        openai_api_key=openai_key,
        openai_base_url=openai_base,
        openai_model=openai_model,
        ollama_host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2").strip(),
        max_tokens_default=int(os.getenv("LLM_MAX_TOKENS", "2048")),
        request_timeout_sec=int(os.getenv("LLM_TIMEOUT_SEC", "120")),
        log_requests=_env_bool("LLM_LOG_REQUESTS", "false"),
    )


def describe_active_provider() -> str:
    """Краткая строка для логов / health (без секретов)."""
    s = load_llm_settings()
    p = s.provider_normalized
    if p == "anthropic":
        return f"anthropic model={s.anthropic_model}"
    if p == "openai":
        return f"openai model={s.openai_model}"
    if p == "openai_compatible":
        url = s.openai_base_url or "(base_url не задан)"
        return f"openai_compatible base={url} model={s.openai_model}"
    if p == "ollama":
        return f"ollama host={s.ollama_host} model={s.ollama_model}"
    return "none (LLM отключён)"
