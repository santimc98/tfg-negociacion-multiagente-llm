"""OpenRouter-backed cloud LLM provider for negotiation actions.

OpenRouter exposes an OpenAI-compatible Chat Completions API, so any model
hosted there (DeepSeek, Kimi K2, GLM, etc.) can act as a negotiation agent
behind the same ``ActionProvider`` interface used by the mock and Ollama
providers. The engine and validator remain the only authority on validity.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from llm.action_parser import LLMActionParseError, invalid_llm_action, parse_llm_action_response
from llm.negotiation_prompt import build_user_prompt, system_prompt
from negotiation.models import (
    AgentRole,
    NegotiationAction,
    ProviderDescriptor,
    Scenario,
    TurnLog,
)


API_KEY_ENV_VAR = "OPENROUTER_API_KEY"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-chat"


class OpenRouterClient(Protocol):
    """Small protocol used to fake OpenRouter in tests."""

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send one chat payload and return the decoded response."""


@dataclass(frozen=True)
class OpenRouterConfig:
    """Runtime configuration for the OpenRouter provider."""

    model_name: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_key: str | None = None
    temperature: float = 0.2
    timeout_seconds: float = 90.0
    history_limit: int = 6
    # Reasoning models (e.g. Kimi) spend many tokens before the answer, so the
    # budget must leave room for the final JSON after the reasoning trace.
    max_tokens: int = 2048
    # Retry malformed/empty model outputs a few times before giving up. This
    # markedly reduces invalid outputs caused by sampling variance.
    max_retries: int = 2
    # Optional OpenRouter "reasoning" control (e.g. {"enabled": False} or
    # {"effort": "low"}) to tame slow/expensive reasoning models for this
    # structured single-action task. None leaves the provider default.
    reasoning: dict[str, Any] | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)

    def resolved_api_key(self) -> str | None:
        """Return the explicit key or fall back to the environment variable."""

        return self.api_key or os.environ.get(API_KEY_ENV_VAR)


class OpenRouterProviderError(RuntimeError):
    """Raised when OpenRouter cannot produce a usable response."""


class HttpOpenRouterClient:
    """Minimal HTTP client for OpenRouter's Chat Completions API."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        timeout_seconds: float,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.extra_headers = extra_headers or {}

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call OpenRouter /chat/completions and return decoded JSON."""

        if not self.api_key:
            raise OpenRouterProviderError(
                f"Missing OpenRouter API key (set {API_KEY_ENV_VAR} or pass api_key)"
            )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            # Optional attribution headers recommended by OpenRouter.
            "HTTP-Referer": "https://github.com/santimc98/tfg-negociacion-multiagente-llm",
            "X-Title": "TFG negociacion multiagente LLM",
        }
        headers.update(self.extra_headers)

        request = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            raise OpenRouterProviderError(
                f"OpenRouter request failed with status {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OpenRouterProviderError(f"OpenRouter request failed: {exc}") from exc


class OpenRouterNegotiationProvider:
    """Cloud LLM provider that emits structured negotiation actions."""

    def __init__(
        self,
        config: OpenRouterConfig | None = None,
        client: OpenRouterClient | None = None,
    ) -> None:
        self.config = config or OpenRouterConfig()
        self.client = client or HttpOpenRouterClient(
            base_url=self.config.base_url,
            api_key=self.config.resolved_api_key(),
            timeout_seconds=self.config.timeout_seconds,
            extra_headers=self.config.extra_headers,
        )

    def describe_provider(self) -> ProviderDescriptor:
        """Return provider metadata for traceability."""

        return ProviderDescriptor(provider_kind="openrouter", model_name=self.config.model_name)

    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        """Generate one action through OpenRouter and parse it safely."""

        payload = self._build_request_payload(
            role=role,
            scenario=scenario,
            round_number=round_number,
            history=history,
        )

        last_error: Exception | None = None
        for _ in range(max(1, self.config.max_retries + 1)):
            try:
                response = self.client.chat(payload)
                content = self._extract_message_content(response)
                return parse_llm_action_response(content, role=role)
            except (LLMActionParseError, OpenRouterProviderError, KeyError, TypeError) as exc:
                last_error = exc
        return invalid_llm_action(role, f"Invalid OpenRouter provider output: {last_error}")

    def _build_request_payload(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
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
            "response_format": {"type": "json_object"},
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
        if self.config.reasoning is not None:
            payload["reasoning"] = self.config.reasoning
        return payload

    def _extract_message_content(self, response: dict[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenRouterProviderError("OpenRouter response has no choices")

        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise OpenRouterProviderError("OpenRouter choice has no message")

        content = message.get("content")
        if isinstance(content, list):
            # Some models return content as a list of parts; join their text.
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterProviderError("OpenRouter message content is empty")

        return _strip_json_fences(content)


def _strip_json_fences(content: str) -> str:
    """Remove markdown code fences that models sometimes wrap JSON in."""

    text = content.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    # Drop the opening fence (``` or ```json) and the closing fence.
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
