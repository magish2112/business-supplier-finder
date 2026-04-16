"""
Проверка упоминания товара на странице сайта (fetch + LLM JSON).

По умолчанию выключено: SITE_CHECK_ENABLED=false.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Optional

import requests

from integrations.llm_client import complete_json

logger = logging.getLogger(__name__)


def _site_check_enabled() -> bool:
    return os.getenv("SITE_CHECK_ENABLED", "false").lower() in ("true", "1", "yes")


def _max_text_chars() -> int:
    raw = os.getenv("SITE_CHECK_MAX_CHARS", "50000").strip() or "50000"
    try:
        return max(1000, min(int(raw), 500_000))
    except ValueError:
        return 50_000


def fetch_url_text(url: str, timeout: float) -> str:
    """
    Загрузка URL и извлечение текста: requests + BeautifulSoup при наличии,
    иначе грубое удаление тегов. Лимит длины — SITE_CHECK_MAX_CHARS.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; BusinessSupplierFinder/1.0; +https://example.local)"
        )
    }
    r = requests.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()
    html = r.text or ""
    max_chars = _max_text_chars()
    text: str
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
    except ImportError:
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars]
    return text


_SITE_JSON_SYSTEM = (
    "You are a precise assistant. Answer with a single JSON object only, no markdown. "
    'Schema: {"mentioned": boolean, "confidence": string, "evidence": string}. '
    "mentioned: whether the product phrase is clearly offered or discussed on the page text. "
    "confidence: one of low|medium|high. evidence: short quote or paraphrase from the text, "
    "or empty if nothing supports it."
)


def check_product_mentioned(url: str, product_phrase: str) -> Dict[str, Any]:
    """
    Загружает страницу и спрашивает LLM (complete_json) про упоминание товара.

    Возвращает словарь с ключами ok, snippet, error; при успехе — также
    mentioned, confidence, evidence из ответа модели.
    """
    if not _site_check_enabled():
        return {"ok": False, "snippet": None, "error": "site_check_disabled"}

    timeout_raw = os.getenv("SITE_CHECK_TIMEOUT_SEC", "8").strip() or "8"
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 8.0
    timeout = max(1.0, min(timeout, 60.0))

    try:
        page_text = fetch_url_text(url, timeout=timeout)
    except Exception as e:
        logger.warning("Не удалось загрузить URL %s: %s", url, e)
        return {"ok": False, "snippet": None, "error": str(e)}

    snippet_preview = (page_text[:2000] + "…") if len(page_text) > 2000 else page_text
    user = (
        f"URL: {url}\n"
        f"Product phrase: {product_phrase}\n\n"
        f"Page text (possibly truncated):\n{page_text[:12000]}"
    )
    raw = complete_json(_SITE_JSON_SYSTEM, user, max_tokens=256)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM вернул не-JSON для проверки сайта: %r", raw[:200])
        return {
            "ok": False,
            "snippet": snippet_preview,
            "error": "llm_invalid_json",
        }

    if not isinstance(data, dict):
        return {"ok": False, "snippet": snippet_preview, "error": "llm_bad_shape"}

    mentioned = data.get("mentioned")
    confidence = data.get("confidence")
    evidence = data.get("evidence")
    if not isinstance(mentioned, bool):
        return {"ok": False, "snippet": snippet_preview, "error": "llm_missing_mentioned"}

    out: Dict[str, Any] = {
        "ok": True,
        "snippet": snippet_preview,
        "error": None,
        "mentioned": mentioned,
        "confidence": confidence if isinstance(confidence, str) else str(confidence),
        "evidence": evidence if isinstance(evidence, str) else str(evidence),
    }
    return out
