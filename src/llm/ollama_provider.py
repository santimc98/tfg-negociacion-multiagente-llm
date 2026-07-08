"""Ollama-backed local LLM provider for negotiation actions."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from llm.action_parser import LLMActionParseError, invalid_llm_action, parse_llm_action_response
from llm.negotiation_prompt import ACTION_JSON_SCHEMA, build_user_prompt, system_prompt
from negotiation.models import (
    AgentRole,
    NegotiationAction,
    ProviderDescriptor,
    Scenario,
    TurnLog,
)

__all__ = [
    "ACTION_JSON_SCHEMA",
    "OllamaConfig",
    "OllamaNegotiationProvider",
    "OllamaProviderError",
    "HttpOllamaClient",
]


class OllamaClient(Protocol):
    """Small protocol used to fake Ollama in tests."""

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send one chat payload and return the decoded response."""


@dataclass(frozen=True)
class OllamaConfig:
    """Runtime configuration for the Ollama provider."""

    model_name: str = "gemma4:26b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.1
    timeout_seconds: float = 60.0
    history_limit: int = 4


class HttpOllamaClient:
    """Minimal HTTP client for Ollama's local API."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call Ollama /api/chat and return decoded JSON."""

        request = urllib.request.Request(
            url=f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OllamaProviderError(f"Ollama request failed: {exc}") from exc


class OllamaProviderError(RuntimeError):
    """Raised when Ollama cannot produce a usable response."""


class OllamaNegotiationProvider:
    """Local LLM provider that emits structured negotiation actions."""

    def __init__(
        self,
        config: OllamaConfig | None = None,
        client: OllamaClient | None = None,
    ) -> None:
        self.config = config or OllamaConfig()
        self.client = client or HttpOllamaClient(
            base_url=self.config.base_url,
            timeout_seconds=self.config.timeout_seconds,
        )

    def describe_provider(self) -> ProviderDescriptor:
        """Return provider metadata for traceability."""

        return ProviderDescriptor(provider_kind="ollama", model_name=self.config.model_name)

    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        """Generate one action through Ollama and parse it safely."""

        payload = self._build_request_payload(
            role=role,
            scenario=scenario,
            round_number=round_number,
            history=history,
        )

        try:
            response = self.client.chat(payload)
            content = self._extract_message_content(response)
            return parse_llm_action_response(content, role=role)
        except (LLMActionParseError, OllamaProviderError, KeyError, TypeError) as exc:
            return invalid_llm_action(role, f"Invalid Ollama provider output: {exc}")

    def _build_request_payload(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> dict[str, Any]:
        return {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt()},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        role=role,
                        scenario=scenario,
                        round_number=round_number,
                        history=history,
                        history_limit=self.config.history_limit,
                    ),
                },
            ],
            "format": ACTION_JSON_SCHEMA,
            "stream": False,
            "options": {"temperature": self.config.temperature},
        }

    def _extract_message_content(self, response: dict[str, Any]) -> str:
        content = response["message"]["content"]
        if not isinstance(content, str):
            raise OllamaProviderError("Ollama message content is not a string")
        return content
