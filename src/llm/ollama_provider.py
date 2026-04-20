"""Ollama-backed local LLM provider for negotiation actions."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from llm.action_parser import LLMActionParseError, invalid_llm_action, parse_llm_action_response
from negotiation.models import AgentRole, NegotiationAction, Scenario, TurnLog
from scenarios.generator import scenario_to_dict


ACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action_type", "offer_terms", "target_offer_id", "rationale"],
    "properties": {
        "action_type": {
            "type": "string",
            "enum": ["PROPOSE", "COUNTER", "ACCEPT", "REJECT", "WALK_AWAY"],
        },
        "target_offer_id": {"type": ["string", "null"]},
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
        "rationale": {"type": ["string", "null"]},
    },
}


class OllamaClient(Protocol):
    """Small protocol used to fake Ollama in tests."""

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send one chat payload and return the decoded response."""


@dataclass(frozen=True)
class OllamaConfig:
    """Runtime configuration for the Ollama provider."""

    model_name: str = "gemma3:27b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.2
    timeout_seconds: float = 60.0


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

    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        """Generate one action through Ollama and parse it safely."""

        payload = {
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

        try:
            response = self.client.chat(payload)
            content = self._extract_message_content(response)
            return parse_llm_action_response(content, role=role)
        except (LLMActionParseError, OllamaProviderError, KeyError, TypeError) as exc:
            return invalid_llm_action(role, f"Invalid Ollama provider output: {exc}")

    def _system_prompt(self) -> str:
        return (
            "You are a negotiation agent in a controlled supply-chain simulation. "
            "Generate exactly one negotiation action. The engine validates all rules; "
            "your task is only to propose a structured action. Respond only with JSON "
            "matching the provided schema."
        )

    def _user_prompt(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> str:
        private_context = self._private_context(role, scenario)
        prompt_payload = {
            "agent_role": role,
            "round_number": round_number,
            "public_scenario": scenario_to_dict(scenario)["constraints"],
            "private_context": private_context,
            "recent_history": self._history_summary(history),
            "output_contract": {
                "action_type": "PROPOSE | COUNTER | ACCEPT | REJECT | WALK_AWAY",
                "target_offer_id": "string or null",
                "offer_terms": {
                    "unit_price": "number",
                    "quantity": "integer",
                    "delivery_deadline": "YYYY-MM-DD",
                },
                "rationale": "short string or null",
            },
            "instructions": [
                "Return only one JSON object.",
                "Use offer_terms only for PROPOSE or COUNTER.",
                "Use target_offer_id for COUNTER, ACCEPT or REJECT.",
                "Do not include proposal_id; the engine assigns it.",
            ],
        }
        return json.dumps(prompt_payload, indent=2, sort_keys=True)

    def _private_context(self, role: AgentRole, scenario: Scenario) -> dict[str, Any]:
        if role == "buyer":
            return {
                "preferences": {
                    "target_unit_price": scenario.buyer_preferences.target_unit_price,
                    "target_quantity": scenario.buyer_preferences.target_quantity,
                    "target_delivery_deadline": (
                        scenario.buyer_preferences.target_delivery_deadline.isoformat()
                    ),
                },
                "guardrails": {
                    "buyer_max_acceptable_unit_price": (
                        scenario.buyer_guardrails.buyer_max_acceptable_unit_price
                    ),
                    "buyer_min_acceptable_quantity": (
                        scenario.buyer_guardrails.buyer_min_acceptable_quantity
                    ),
                    "buyer_latest_acceptable_deadline": (
                        scenario.buyer_guardrails.buyer_latest_acceptable_deadline.isoformat()
                    ),
                },
            }

        return {
            "preferences": {
                "target_unit_price": scenario.seller_preferences.target_unit_price,
                "target_quantity": scenario.seller_preferences.target_quantity,
                "target_delivery_deadline": (
                    scenario.seller_preferences.target_delivery_deadline.isoformat()
                ),
            },
            "guardrails": {
                "seller_min_acceptable_unit_price": (
                    scenario.seller_guardrails.seller_min_acceptable_unit_price
                ),
                "seller_min_acceptable_quantity": (
                    scenario.seller_guardrails.seller_min_acceptable_quantity
                ),
                "seller_earliest_acceptable_deadline": (
                    scenario.seller_guardrails.seller_earliest_acceptable_deadline.isoformat()
                ),
            },
        }

    def _history_summary(self, history: tuple[TurnLog, ...]) -> list[dict[str, Any]]:
        return [
            {
                "round_number": turn.round_number,
                "agent_role": turn.agent_role,
                "action_type": turn.action.action_type.value
                if hasattr(turn.action.action_type, "value")
                else str(turn.action.action_type),
                "proposal_id": turn.action.proposal_id,
                "target_offer_id": turn.action.target_offer_id,
                "offer_terms": self._offer_terms_dict(turn.action.offer_terms),
                "is_valid": turn.is_valid,
                "state": turn.negotiation_state,
                "summary": turn.result_summary,
            }
            for turn in history[-8:]
        ]

    def _offer_terms_dict(self, offer_terms: Any) -> dict[str, Any] | None:
        if offer_terms is None:
            return None
        return {
            "unit_price": offer_terms.unit_price,
            "quantity": offer_terms.quantity,
            "delivery_deadline": offer_terms.delivery_deadline.isoformat(),
        }

    def _extract_message_content(self, response: dict[str, Any]) -> str:
        content = response["message"]["content"]
        if not isinstance(content, str):
            raise OllamaProviderError("Ollama message content is not a string")
        return content
