"""Registro de provedores. Estratégia = ``provedor:modelo`` (ex.: ``anthropic:claude-haiku-4-5``)"""

from __future__ import annotations

from llm.providers.anthropic import AnthropicProvider
from llm.providers.base import Provider
from llm.providers.gemini import GeminiProvider
from llm.providers.ollama import OllamaProvider
from llm.types import LLMError

RULES = "rules"  # estratégia sem LLM: função Python da tarefa


def default_providers(client=None) -> dict[str, Provider]:
    return {
        "gemini-free": GeminiProvider(paid=False, client=client),
        "gemini-paid": GeminiProvider(paid=True, client=client),
        "anthropic": AnthropicProvider(client=client),
        "ollama": OllamaProvider(client=client),
    }


def split_strategy(spec: str) -> tuple[str, str]:
    """``"gemini-free:gemini-2.5-flash-lite"`` -> (``"gemini-free"``, ``"gemini-2.5-flash-lite"``).

    O modelo pode ter ``:`` (ex. ``ollama:qwen2.5:7b``); ``rules`` não tem modelo.
    """
    provider, _, model = spec.partition(":")
    if provider != RULES and not model:
        raise LLMError(f"estratégia inválida «{spec}» (use provedor:modelo)")
    return provider, model
