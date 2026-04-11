"""
Обратная совместимость: раньше здесь был только Claude.

Сейчас используйте integrations.llm_client (провайдер задаётся LLM_PROVIDER).
"""

from integrations.llm_client import complete_json  # noqa: F401

__all__ = ["complete_json"]
