"""Parser for structured LLM negotiation actions."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from negotiation.models import AgentRole, NegotiationAction, NegotiationActionType, OfferTerms


class LLMActionParseError(ValueError):
    """Raised when an LLM response cannot be converted into an action."""


MAX_RATIONALE_LENGTH = 160


def parse_llm_action_response(response: str | dict[str, Any], role: AgentRole) -> NegotiationAction:
    """Parse a JSON LLM response into a NegotiationAction."""

    payload = _load_payload(response)
    action_type = _parse_action_type(payload.get("action_type"))
    offer_terms = _parse_offer_terms(payload.get("offer_terms"))
    target_offer_id = _parse_optional_string(payload.get("target_offer_id"), "target_offer_id")
    rationale = _parse_optional_string(payload.get("rationale"), "rationale")

    return NegotiationAction(
        agent_role=role,
        action_type=action_type,
        offer_terms=offer_terms,
        target_offer_id=target_offer_id,
        rationale=rationale,
    )


def invalid_llm_action(role: AgentRole, reason: str) -> NegotiationAction:
    """Create an intentionally invalid action that the engine will reject."""

    return NegotiationAction(
        agent_role=role,
        action_type="INVALID_LLM_OUTPUT",  # type: ignore[arg-type]
        rationale=reason,
    )


def _load_payload(response: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if not isinstance(response, str):
        raise LLMActionParseError("LLM response must be a JSON string or dict")

    try:
        payload = json.loads(response)
    except json.JSONDecodeError as exc:
        raise LLMActionParseError("LLM response is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise LLMActionParseError("LLM response JSON must be an object")
    return payload


def _parse_action_type(raw_value: Any) -> NegotiationActionType:
    if not isinstance(raw_value, str):
        raise LLMActionParseError("action_type must be a string")

    try:
        return NegotiationActionType(raw_value.upper())
    except ValueError as exc:
        raise LLMActionParseError("action_type is not a supported negotiation action") from exc


def _parse_offer_terms(raw_value: Any) -> OfferTerms | None:
    if raw_value is None:
        return None
    if not isinstance(raw_value, dict):
        raise LLMActionParseError("offer_terms must be an object or null")

    unit_price = raw_value.get("unit_price")
    quantity = raw_value.get("quantity")
    delivery_deadline = raw_value.get("delivery_deadline")

    if not isinstance(unit_price, (int, float)) or isinstance(unit_price, bool):
        raise LLMActionParseError("offer_terms.unit_price must be numeric")
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        raise LLMActionParseError("offer_terms.quantity must be an integer")
    if not isinstance(delivery_deadline, str):
        raise LLMActionParseError("offer_terms.delivery_deadline must be an ISO date string")

    try:
        parsed_deadline = date.fromisoformat(delivery_deadline)
    except ValueError as exc:
        raise LLMActionParseError("offer_terms.delivery_deadline must be a valid ISO date") from exc

    return OfferTerms(
        unit_price=float(unit_price),
        quantity=quantity,
        delivery_deadline=parsed_deadline,
    )


def _parse_optional_string(raw_value: Any, field_name: str) -> str | None:
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        raise LLMActionParseError(f"{field_name} must be a string or null")
    normalized = " ".join(raw_value.strip().split())
    if normalized == "":
        return None
    if field_name == "rationale" and len(normalized) > MAX_RATIONALE_LENGTH:
        raise LLMActionParseError("rationale must be brief")
    return normalized
