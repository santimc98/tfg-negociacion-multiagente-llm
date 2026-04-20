"""Validation rules for terms, actions and agreements."""

from __future__ import annotations

from collections.abc import Container, Mapping
from dataclasses import dataclass
from datetime import date

from negotiation.models import (
    Agreement,
    AgentRole,
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
    proposal_owner_by_id: Mapping[str, AgentRole] | None = None,
    rejected_offer_ids: Container[str] | None = None,
) -> ValidationResult:
    """Validate action structure and referenced proposal IDs.

    REJECT is modeled as a specific rejection of a prior proposal, so it
    requires target_offer_id. WALK_AWAY remains the generic terminal refusal.
    """

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

    if action.action_type == NegotiationActionType.PROPOSE and action.target_offer_id is not None:
        errors.append("PROPOSE must not include target_offer_id")

    if action.action_type == NegotiationActionType.COUNTER:
        if not action.target_offer_id:
            errors.append("COUNTER requires target_offer_id")
        else:
            errors.extend(
                _validate_target_reference(
                    action=action,
                    valid_offer_ids=valid_offer_ids,
                    proposal_owner_by_id=proposal_owner_by_id,
                    rejected_offer_ids=None,
                    action_name="COUNTER",
                )
            )

    if action.action_type == NegotiationActionType.ACCEPT:
        if not action.target_offer_id:
            errors.append("ACCEPT requires target_offer_id")
        else:
            errors.extend(
                _validate_target_reference(
                    action=action,
                    valid_offer_ids=valid_offer_ids,
                    proposal_owner_by_id=proposal_owner_by_id,
                    rejected_offer_ids=rejected_offer_ids,
                    action_name="ACCEPT",
                )
            )
        if action.offer_terms is not None:
            errors.append("ACCEPT must not include offer_terms")

    if action.action_type == NegotiationActionType.REJECT:
        if not action.target_offer_id:
            errors.append("REJECT requires target_offer_id")
        else:
            errors.extend(
                _validate_target_reference(
                    action=action,
                    valid_offer_ids=valid_offer_ids,
                    proposal_owner_by_id=proposal_owner_by_id,
                    rejected_offer_ids=None,
                    action_name="REJECT",
                )
            )
        if action.offer_terms is not None:
            errors.append("REJECT must not include offer_terms")

    if action.action_type == NegotiationActionType.WALK_AWAY:
        if action.offer_terms is not None:
            errors.append("WALK_AWAY must not include offer_terms")
        if action.target_offer_id is not None:
            errors.append("WALK_AWAY must not include target_offer_id")

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


def validate_terms_for_buyer_acceptance(
    terms: OfferTerms,
    scenario: Scenario,
) -> ValidationResult:
    """Validate terms against the buyer's private reservation limits."""

    errors: list[str] = []
    guardrails = scenario.buyer_guardrails

    if terms.unit_price > guardrails.buyer_max_acceptable_unit_price:
        errors.append("unit_price exceeds buyer maximum acceptable price")
    if terms.quantity < guardrails.buyer_min_acceptable_quantity:
        errors.append("quantity is below buyer minimum acceptable quantity")
    if terms.delivery_deadline > guardrails.buyer_latest_acceptable_deadline:
        errors.append("delivery_deadline is later than buyer latest acceptable deadline")

    return ValidationResult(is_valid=not errors, errors=tuple(errors))


def validate_terms_for_seller_acceptance(
    terms: OfferTerms,
    scenario: Scenario,
) -> ValidationResult:
    """Validate terms against the seller's private reservation limits."""

    errors: list[str] = []
    guardrails = scenario.seller_guardrails

    if terms.unit_price < guardrails.seller_min_acceptable_unit_price:
        errors.append("unit_price is below seller minimum acceptable price")
    if terms.quantity < guardrails.seller_min_acceptable_quantity:
        errors.append("quantity is below seller minimum acceptable quantity")
    if terms.delivery_deadline < guardrails.seller_earliest_acceptable_deadline:
        errors.append("delivery_deadline is earlier than seller earliest acceptable deadline")

    return ValidationResult(is_valid=not errors, errors=tuple(errors))


def validate_terms_for_acceptance(
    role: AgentRole,
    terms: OfferTerms,
    scenario: Scenario,
) -> ValidationResult:
    """Validate accepted terms against the accepting agent's guardrails."""

    if role == "buyer":
        return validate_terms_for_buyer_acceptance(terms, scenario)
    if role == "seller":
        return validate_terms_for_seller_acceptance(terms, scenario)
    return ValidationResult(False, ("agent_role must be 'buyer' or 'seller'",))


def _validate_target_reference(
    action: NegotiationAction,
    valid_offer_ids: Container[str] | None,
    proposal_owner_by_id: Mapping[str, AgentRole] | None,
    rejected_offer_ids: Container[str] | None,
    action_name: str,
) -> tuple[str, ...]:
    errors: list[str] = []

    if action.target_offer_id is None:
        return (f"{action_name} requires target_offer_id",)

    if valid_offer_ids is not None and action.target_offer_id not in valid_offer_ids:
        errors.append(f"{action_name} target_offer_id must reference a valid proposal")

    if proposal_owner_by_id is not None and action.target_offer_id in proposal_owner_by_id:
        if proposal_owner_by_id[action.target_offer_id] == action.agent_role:
            errors.append(f"{action_name} must target a proposal from the counterparty")

    if rejected_offer_ids is not None and action.target_offer_id in rejected_offer_ids:
        errors.append(f"{action_name} must not target a rejected proposal")

    return tuple(errors)
