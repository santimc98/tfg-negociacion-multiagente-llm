"""Shared prompt construction for LLM negotiation providers.

Both the Ollama and OpenRouter providers build the same structured request:
public ranges, private role context, operational rules and a short recent
history. Centralising this keeps every LLM provider consistent and makes the
information flow easy to document and diagram.
"""

from __future__ import annotations

import json
from typing import Any

from negotiation.models import AgentRole, Scenario, TurnLog


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


def system_prompt() -> str:
    """Return the shared system instruction for negotiation providers."""

    return (
        "You are an agent in a supply-chain negotiation. "
        "Return exactly one JSON object with EXACTLY these four keys, no others, no renaming: "
        '"action_type" (one of PROPOSE, COUNTER, ACCEPT, REJECT, WALK_AWAY), '
        '"target_offer_id" (string or null), '
        '"offer_terms" (object with "unit_price" number, "quantity" integer, '
        '"delivery_deadline" string "YYYY-MM-DD"; or null), '
        '"rationale" (null or one short sentence written IN SPANISH). '
        "The rationale must always be written in Spanish. "
        "Do not add extra fields. Do not include explanations or internal reasoning outside the JSON. "
        "If you cannot produce a valid action, return action_type WALK_AWAY with rationale null."
    )


def build_user_prompt(
    role: AgentRole,
    scenario: Scenario,
    round_number: int,
    history: tuple[TurnLog, ...],
    history_limit: int,
) -> str:
    """Build the compact JSON user prompt sent to the model."""

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
        "private_context": private_context(role, scenario),
        "history": history_summary(role, history, history_limit),
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


def private_context(role: AgentRole, scenario: Scenario) -> dict[str, Any]:
    """Return the private targets and guardrails for one role."""

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


def history_summary(
    role: AgentRole,
    history: tuple[TurnLog, ...],
    history_limit: int,
) -> list[dict[str, Any]]:
    """Summarise the most recent relevant turns for the prompt."""

    recent_turns = history[-history_limit:] if history_limit > 0 else ()
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
            "offer_terms": _offer_terms_dict(turn.action.offer_terms),
            "valid": turn.is_valid,
            "summary": _compact_summary(turn.result_summary),
        }
        for turn in recent_turns
        if turn.agent_role == role or turn.action.proposal_id or turn.action.target_offer_id
    ]


def _offer_terms_dict(offer_terms: Any) -> dict[str, Any] | None:
    if offer_terms is None:
        return None
    return {
        "unit_price": offer_terms.unit_price,
        "quantity": offer_terms.quantity,
        "delivery_deadline": offer_terms.delivery_deadline.isoformat(),
    }


def _compact_summary(summary: str) -> str:
    return " ".join(summary.split())[:120]
