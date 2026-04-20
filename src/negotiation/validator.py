"""Validation rules for terms, actions and agreements."""

from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass
from datetime import date

from negotiation.models import (
    Agreement,
    NegotiationAction,
    NegotiationActionType,
    OfferTerms,
    Scenario,
)


@dataclass(frozen=True)
class ValidationResult:
    """Result of a validation operation."""

    is_valid: bool
    errors: tuple[str, ...] = ()


def validate_offer_terms(terms: OfferTerms, scenario: Scenario) -> ValidationResult:
    """Validate negotiable terms against hard scenario constraints."""

    errors: list[str] = []
    constraints = scenario.constraints

    if terms.unit_price <= 0:
        errors.append("unit_price must be greater than 0")

    if not isinstance(terms.quantity, int) or isinstance(terms.quantity, bool):
        errors.append("quantity must be an integer")
    elif terms.quantity <= 0:
        errors.append("quantity must be positive")

    if not isinstance(terms.delivery_deadline, date):
        errors.append("delivery_deadline must be a date")

    if terms.unit_price < constraints.min_unit_price:
        errors.append("unit_price is below scenario minimum")
    if terms.unit_price > constraints.max_unit_price:
        errors.append("unit_price is above scenario maximum")

    if isinstance(terms.quantity, int) and not isinstance(terms.quantity, bool):
        if terms.quantity < constraints.min_quantity:
            errors.append("quantity is below scenario minimum")
        if terms.quantity > constraints.max_quantity:
            errors.append("quantity is above scenario maximum")

    if isinstance(terms.delivery_deadline, date):
        if terms.delivery_deadline < constraints.earliest_delivery_deadline:
            errors.append("delivery_deadline is earlier than scenario minimum")
        if terms.delivery_deadline > constraints.latest_delivery_deadline:
            errors.append("delivery_deadline is later than scenario maximum")

    return ValidationResult(is_valid=not errors, errors=tuple(errors))


def validate_action(
    action: NegotiationAction,
    scenario: Scenario,
    valid_offer_ids: Container[str] | None = None,
) -> ValidationResult:
    """Validate action structure and referenced proposal IDs."""

    errors: list[str] = []

    if action.agent_role not in {"buyer", "seller"}:
        errors.append("agent_role must be 'buyer' or 'seller'")

    if not isinstance(action.action_type, NegotiationActionType):
        errors.append("action_type must be a NegotiationActionType")
        return ValidationResult(is_valid=False, errors=tuple(errors))

    if action.action_type in {NegotiationActionType.PROPOSE, NegotiationActionType.COUNTER}:
        if action.offer_terms is None:
            errors.append(f"{action.action_type.value} requires offer_terms")
        else:
            errors.extend(validate_offer_terms(action.offer_terms, scenario).errors)

    if action.action_type == NegotiationActionType.ACCEPT:
        if not action.target_offer_id:
            errors.append("ACCEPT requires target_offer_id")
        elif valid_offer_ids is not None and action.target_offer_id not in valid_offer_ids:
            errors.append("ACCEPT target_offer_id must reference a valid proposal")
        if action.offer_terms is not None:
            errors.append("ACCEPT must not include offer_terms")

    if action.action_type in {NegotiationActionType.REJECT, NegotiationActionType.WALK_AWAY}:
        if action.offer_terms is not None:
            errors.append(f"{action.action_type.value} must not include offer_terms")

    return ValidationResult(is_valid=not errors, errors=tuple(errors))


def validate_agreement(agreement: Agreement, scenario: Scenario) -> ValidationResult:
    """Validate agreement terms and acceptance metadata explicitly."""

    errors: list[str] = []

    if not agreement.accepted_offer_id:
        errors.append("accepted_offer_id is required")
    if agreement.proposed_by not in {"buyer", "seller"}:
        errors.append("proposed_by must be 'buyer' or 'seller'")
    if agreement.accepted_by not in {"buyer", "seller"}:
        errors.append("accepted_by must be 'buyer' or 'seller'")
    if agreement.proposed_by == agreement.accepted_by:
        errors.append("agreement must be accepted by the counterparty")
    if agreement.reached_at_round <= 0:
        errors.append("reached_at_round must be positive")

    errors.extend(validate_offer_terms(agreement.terms, scenario).errors)

    return ValidationResult(is_valid=not errors, errors=tuple(errors))
