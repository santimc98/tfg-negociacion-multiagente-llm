"""Ollama-backed local LLM provider for negotiation actions."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from llm.action_parser import LLMActionParseError, invalid_llm_action, parse_llm_action_response
from negotiation.models import (
    AgentRole,
    NegotiationAction,
    ProviderDescriptor,
    Scenario,
    TurnLog,
)


ACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action_type", "target_offer_id", "offer_terms", "rationale"],
    "properties": {
        "action_type": {
            "type": "string",
            "enum": ["PROPOSE", "COUNTER", "ACCEPT", "REJECT", "WALK_AWAY"],
        },
        "target_offer_id": {
            "type": ["string", "null"],
            "maxLength": 32,
        },
        "offer_terms": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["unit_price", "quantity", "delivery_deadline"],
            "properties": {
                "unit_price": {"type": "number"},
                "quantity": {"type": "integer"},
                "delivery_deadline": {"type": "string", "format": "date"},
            },
        },
        "rationale": {
            "type": ["string", "null"],
            "maxLength": 160,
        },
    },
}


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
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": self._user_prompt(
                        role=role,
                        scenario=scenario,
                        round_number=round_number,
                        history=history,
                    ),
                },
            ],
            "format": ACTION_JSON_SCHEMA,
            "stream": False,
            "options": {"temperature": self.config.temperature},
        }

    def _system_prompt(self) -> str:
        return (
            "Return exactly one JSON action for a supply negotiation. "
            "Do not explain. Do not include internal reasoning, drafts or extra fields. "
            "If you cannot produce a valid action, return WALK_AWAY with rationale null."
        )

    def _user_prompt(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> str:
        constraints = scenario.constraints
        prompt_payload = {
            "role": role,
            "round": round_number,
            "public_ranges": {
                "unit_price": [constraints.min_unit_price, constraints.max_unit_price],
                "quantity": [constraints.min_quantity, constraints.max_quantity],
                "delivery_deadline": [
                    constraints.earliest_delivery_deadline.isoformat(),
                    constraints.latest_delivery_deadline.isoformat(),
                ],
            },
            "private_context": self._private_context(role, scenario),
            "history": self._history_summary(role, history),
            "rules": [
                "PROPOSE: offer_terms required, target_offer_id null.",
                "COUNTER: offer_terms required, target_offer_id required.",
                "ACCEPT: target_offer_id required, offer_terms null.",
                "REJECT: target_offer_id required, offer_terms null.",
                "WALK_AWAY: target_offer_id null, offer_terms null.",
                "rationale should be null or one short sentence.",
                "Never include internal reasoning.",
            ],
        }
        return json.dumps(prompt_payload, separators=(",", ":"), sort_keys=True)

    def _private_context(self, role: AgentRole, scenario: Scenario) -> dict[str, Any]:
        if role == "buyer":
            return {
                "target": {
                    "unit_price": scenario.buyer_preferences.target_unit_price,
                    "quantity": scenario.buyer_preferences.target_quantity,
                    "delivery_deadline": (
                        scenario.buyer_preferences.target_delivery_deadline.isoformat()
                    ),
                },
                "guardrails": {
                    "max_unit_price": scenario.buyer_guardrails.buyer_max_acceptable_unit_price,
                    "min_quantity": scenario.buyer_guardrails.buyer_min_acceptable_quantity,
                    "latest_deadline": (
                        scenario.buyer_guardrails.buyer_latest_acceptable_deadline.isoformat()
                    ),
                },
            }

        return {
            "target": {
                "unit_price": scenario.seller_preferences.target_unit_price,
                "quantity": scenario.seller_preferences.target_quantity,
                "delivery_deadline": (
                    scenario.seller_preferences.target_delivery_deadline.isoformat()
                ),
            },
            "guardrails": {
                "min_unit_price": scenario.seller_guardrails.seller_min_acceptable_unit_price,
                "min_quantity": scenario.seller_guardrails.seller_min_acceptable_quantity,
                "earliest_deadline": (
                    scenario.seller_guardrails.seller_earliest_acceptable_deadline.isoformat()
                ),
            },
        }

    def _history_summary(
        self,
        role: AgentRole,
        history: tuple[TurnLog, ...],
    ) -> list[dict[str, Any]]:
        recent_turns = history[-self.config.history_limit :] if self.config.history_limit > 0 else ()
        return [
            {
                "r": turn.round_number,
                "agent": turn.agent_role,
                "action": turn.action.action_type.value
                if hasattr(turn.action.action_type, "value")
                else str(turn.action.action_type),
                "proposal_id": turn.action.proposal_id,
                "target_offer_id": turn.action.target_offer_id,
                "target_offer_id_resolved": turn.target_offer_id_resolved,
                "offer_terms": self._offer_terms_dict(turn.action.offer_terms),
                "valid": turn.is_valid,
                "summary": self._compact_summary(turn.result_summary),
            }
            for turn in recent_turns
            if turn.agent_role == role or turn.action.proposal_id or turn.action.target_offer_id
        ]

    def _offer_terms_dict(self, offer_terms: Any) -> dict[str, Any] | None:
        if offer_terms is None:
            return None
        return {
            "unit_price": offer_terms.unit_price,
            "quantity": offer_terms.quantity,
            "delivery_deadline": offer_terms.delivery_deadline.isoformat(),
        }

    def _compact_summary(self, summary: str) -> str:
        return " ".join(summary.split())[:120]

    def _extract_message_content(self, response: dict[str, Any]) -> str:
        content = response["message"]["content"]
        if not isinstance(content, str):
            raise OllamaProviderError("Ollama message content is not a string")
        return content
