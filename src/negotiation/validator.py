"""Validation rules for offers and agreements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from negotiation.models import Agreement, Offer, Scenario


@dataclass(frozen=True)
class ValidationResult:
    """Result of a validation operation."""

    is_valid: bool
    errors: tuple[str, ...] = ()


def validate_offer(offer: Offer, scenario: Scenario) -> ValidationResult:
    """Validate an offer against basic and scenario constraints."""

    errors: list[str] = []

    if offer.agent_role not in {"buyer", "seller"}:
        errors.append("agent_role must be 'buyer' or 'seller'")

    if offer.unit_price <= 0:
        errors.append("unit_price must be greater than 0")

    if not isinstance(offer.quantity, int) or isinstance(offer.quantity, bool):
        errors.append("quantity must be an integer")
    elif offer.quantity <= 0:
        errors.append("quantity must be positive")

    if not isinstance(offer.delivery_deadline, date):
        errors.append("delivery_deadline must be a date")

    if offer.unit_price < scenario.min_unit_price:
        errors.append("unit_price is below scenario minimum")
    if offer.unit_price > scenario.max_unit_price:
        errors.append("unit_price is above scenario maximum")

    if isinstance(offer.quantity, int) and not isinstance(offer.quantity, bool):
        if offer.quantity < scenario.min_quantity:
            errors.append("quantity is below scenario minimum")
        if offer.quantity > scenario.max_quantity:
            errors.append("quantity is above scenario maximum")

    if isinstance(offer.delivery_deadline, date):
        if offer.delivery_deadline < scenario.earliest_delivery_deadline:
            errors.append("delivery_deadline is earlier than scenario minimum")
        if offer.delivery_deadline > scenario.latest_delivery_deadline:
            errors.append("delivery_deadline is later than scenario maximum")

    return ValidationResult(is_valid=not errors, errors=tuple(errors))


def validate_agreement(agreement: Agreement, scenario: Scenario) -> ValidationResult:
    """Validate agreement terms using the same hard scenario bounds."""

    synthetic_offer = Offer(
        agent_role="buyer",
        unit_price=agreement.unit_price,
        quantity=agreement.quantity,
        delivery_deadline=agreement.delivery_deadline,
    )
    return validate_offer(synthetic_offer, scenario)
