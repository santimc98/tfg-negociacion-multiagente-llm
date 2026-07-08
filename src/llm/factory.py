"""Provider factory for mock, Ollama and OpenRouter negotiation providers."""

from __future__ import annotations

from typing import Literal

from llm.ollama_provider import OllamaConfig, OllamaNegotiationProvider
from llm.openrouter_provider import (
    DEFAULT_BASE_URL as OPENROUTER_DEFAULT_BASE_URL,
    DEFAULT_MODEL as OPENROUTER_DEFAULT_MODEL,
    OpenRouterConfig,
    OpenRouterNegotiationProvider,
)
from llm.provider import MockNegotiationProvider
from negotiation.engine import ActionProvider


ProviderKind = Literal["mock", "ollama", "openrouter"]


def create_provider(
    provider_kind: ProviderKind = "mock",
    model_name: str = "gemma4:26b",
    base_url: str | None = None,
    temperature: float = 0.1,
    timeout_seconds: float = 60.0,
    history_limit: int = 4,
    api_key: str | None = None,
    reasoning: dict | None = None,
) -> ActionProvider:
    """Create a negotiation action provider by name."""

    if provider_kind == "mock":
        return MockNegotiationProvider()
    if provider_kind == "ollama":
        return OllamaNegotiationProvider(
            config=OllamaConfig(
                model_name=model_name,
                base_url=base_url or "http://localhost:11434",
                temperature=temperature,
                timeout_seconds=timeout_seconds,
                history_limit=history_limit,
            )
        )
    if provider_kind == "openrouter":
        return OpenRouterNegotiationProvider(
            config=OpenRouterConfig(
                model_name=model_name if model_name else OPENROUTER_DEFAULT_MODEL,
                base_url=base_url or OPENROUTER_DEFAULT_BASE_URL,
                api_key=api_key,
                temperature=temperature,
                timeout_seconds=timeout_seconds,
                history_limit=history_limit,
                reasoning=reasoning,
            )
        )
    raise ValueError(f"Unknown provider_kind: {provider_kind}")
