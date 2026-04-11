"""
Унифицированный вызов модели для JSON-ответов (оркестрация, черновики писем).

Провайдер задаётся LLM_PROVIDER; ключи и URL — в integrations.llm_config / .env.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import requests

from integrations.llm_config import LLMSettings, load_llm_settings

logger = logging.getLogger(__name__)


def _log(s: LLMSettings, msg: str, *args: Any) -> None:
    if s.log_requests:
        logger.info(msg, *args)
    else:
        logger.debug(msg, *args)


def _complete_anthropic(system: str, user: str, max_tokens: int, s: LLMSettings) -> str:
    try:
        import anthropic  # type: ignore
    except ImportError:
        logger.warning("LLM_PROVIDER=anthropic, но пакет anthropic не установлен.")
        return "{}"
    if not s.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY не задан.")
        return "{}"
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    message = client.messages.create(
        model=s.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts: List[str] = []
    for block in getattr(message, "content", None) or []:
        t = getattr(block, "text", None)
        if t:
            parts.append(t)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts).strip() or "{}"


def _complete_openai_chat(
    system: str,
    user: str,
    max_tokens: int,
    *,
    api_key: str,
    model: str,
    base_url: Optional[str],
    timeout: int,
    label: str,
) -> str:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        logger.warning("Пакет openai не установлен (%s).", label)
        return "{}"
    if not api_key:
        logger.warning("OPENAI_API_KEY не задан (%s).", label)
        return "{}"
    kwargs: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    try:
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            timeout=timeout,
        )
    except Exception as e:
        logger.warning("Ошибка %s API: %s", label, e)
        return "{}"
    choice = resp.choices[0].message
    content = (choice.content or "").strip() if choice else ""
    return content or "{}"


def _complete_ollama(system: str, user: str, max_tokens: int, s: LLMSettings) -> str:
    url = f"{s.ollama_host}/api/chat"
    payload = {
        "model": s.ollama_model,
        "stream": False,
        "options": {"num_predict": max_tokens},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        r = requests.post(url, json=payload, timeout=s.request_timeout_sec)
        r.raise_for_status()
        data = r.json()
        msg = data.get("message") or {}
        text = (msg.get("content") or "").strip()
        return text or "{}"
    except Exception as e:
        logger.warning("Ошибка Ollama (%s): %s", url, e)
        return "{}"


def complete_json(system: str, user: str, max_tokens: int) -> str:
    """
    Запрос к выбранному провайдеру. Ожидается текст с JSON (парсинг снаружи).

    При провайдере none, ошибке или отсутствии зависимостей возвращает "{}".
    """
    s = load_llm_settings()
    p = s.provider_normalized
    mt = max_tokens if max_tokens > 0 else s.max_tokens_default
    _log(s, "LLM complete_json provider=%s max_tokens=%s", p, mt)

    if p == "none":
        logger.debug("LLM_PROVIDER=none, пропуск вызова модели.")
        return "{}"

    if p == "anthropic":
        try:
            return _complete_anthropic(system, user, mt, s)
        except Exception as e:
            logger.warning("Ошибка Anthropic: %s", e)
            return "{}"

    if p == "openai":
        return _complete_openai_chat(
            system,
            user,
            mt,
            api_key=s.openai_api_key,
            model=s.openai_model,
            base_url=None,
            timeout=s.request_timeout_sec,
            label="OpenAI",
        )

    if p == "openai_compatible":
        if not s.openai_base_url:
            logger.warning("OPENAI_BASE_URL обязателен для LLM_PROVIDER=openai_compatible.")
            return "{}"
        return _complete_openai_chat(
            system,
            user,
            mt,
            api_key=s.openai_api_key,
            model=s.openai_model,
            base_url=s.openai_base_url,
            timeout=s.request_timeout_sec,
            label="OpenAI-compatible",
        )

    if p == "ollama":
        return _complete_ollama(system, user, mt, s)

    logger.warning("Неизвестный LLM_PROVIDER=%r, используйте anthropic|openai|openai_compatible|ollama|none.", p)
    return "{}"
