"""Provider factory for mock and Ollama negotiation providers."""

from __future__ import annotations

from typing import Literal

from llm.ollama_provider import OllamaConfig, OllamaNegotiationProvider
from llm.provider import MockNegotiationProvider
from negotiation.engine import ActionProvider


ProviderKind = Literal["mock", "ollama"]


def create_provider(
    provider_kind: ProviderKind = "mock",
    model_name: str = "gemma4:26b",
    base_url: str = "http://localhost:11434",
    temperature: float = 0.1,
    timeout_seconds: float = 60.0,
    history_limit: int = 4,
) -> ActionProvider:
    """Create a negotiation action provider by name."""

    if provider_kind == "mock":
        return MockNegotiationProvider()
    if provider_kind == "ollama":
        return OllamaNegotiationProvider(
            config=OllamaConfig(
                model_name=model_name,
                base_url=base_url,
                temperature=temperature,
                timeout_seconds=timeout_seconds,
                history_limit=history_limit,
            )
        )
    raise ValueError(f"Unknown provider_kind: {provider_kind}")
