"""Basic metrics for negotiation results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from negotiation.models import Agreement, NegotiationResult, Scenario
from negotiation.validator import (
    validate_agreement,
    validate_terms_for_buyer_acceptance,
    validate_terms_for_seller_acceptance,
)


@dataclass(frozen=True)
class NegotiationMetrics:
    """Quantitative summary of a negotiation result."""

    agreement_reached: bool
    valid_agreement: bool
    rounds_used: int
    buyer_utility: float
    seller_utility: float
    joint_utility: float
    private_feasibility_buyer: bool
    private_feasibility_seller: bool
    agreement_balance_gap: float


def calculate_metrics(result: NegotiationResult) -> NegotiationMetrics:
    """Calculate basic outcome and utility metrics."""

    agreement = result.agreement
    valid_agreement = agreement is not None and validate_agreement(agreement, result.scenario).is_valid
    private_feasibility_buyer = (
        agreement is not None
        and validate_terms_for_buyer_acceptance(agreement.terms, result.scenario).is_valid
    )
    private_feasibility_seller = (
        agreement is not None
        and validate_terms_for_seller_acceptance(agreement.terms, result.scenario).is_valid
    )
    buyer_utility = _buyer_utility(agreement, result.scenario) if valid_agreement else 0.0
    seller_utility = _seller_utility(agreement, result.scenario) if valid_agreement else 0.0

    return NegotiationMetrics(
        agreement_reached=agreement is not None,
        valid_agreement=valid_agreement,
        rounds_used=_rounds_used(result),
        buyer_utility=buyer_utility,
        seller_utility=seller_utility,
        joint_utility=round(buyer_utility + seller_utility, 4),
        private_feasibility_buyer=private_feasibility_buyer,
        private_feasibility_seller=private_feasibility_seller,
        agreement_balance_gap=round(abs(buyer_utility - seller_utility), 4),
    )


def _rounds_used(result: NegotiationResult) -> int:
    if result.agreement is not None:
        return result.agreement.reached_at_round
    if not result.turn_log:
        return 0
    return max(turn.round_number for turn in result.turn_log)


def _buyer_utility(agreement: Agreement | None, scenario: Scenario) -> float:
    if agreement is None:
        return 0.0

    constraints = scenario.constraints
    preferences = scenario.buyer_preferences
    terms = agreement.terms
    price_score = 1 - _normalized(
        terms.unit_price,
        constraints.min_unit_price,
        constraints.max_unit_price,
    )
    quantity_score = _target_score(
        terms.quantity,
        preferences.target_quantity,
        constraints.min_quantity,
        constraints.max_quantity,
    )
    deadline_score = 1 - _date_normalized(
        terms.delivery_deadline,
        constraints.earliest_delivery_deadline,
        constraints.latest_delivery_deadline,
    )

    return round((price_score + quantity_score + deadline_score) / 3, 4)


def _seller_utility(agreement: Agreement | None, scenario: Scenario) -> float:
    if agreement is None:
        return 0.0

    constraints = scenario.constraints
    preferences = scenario.seller_preferences
    terms = agreement.terms
    price_score = _normalized(
        terms.unit_price,
        constraints.min_unit_price,
        constraints.max_unit_price,
    )
    quantity_score = _target_score(
        terms.quantity,
        preferences.target_quantity,
        constraints.min_quantity,
        constraints.max_quantity,
    )
    deadline_score = _date_normalized(
        terms.delivery_deadline,
        constraints.earliest_delivery_deadline,
        constraints.latest_delivery_deadline,
    )

    return round((price_score + quantity_score + deadline_score) / 3, 4)


def _normalized(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 1.0
    return _clamp((value - minimum) / (maximum - minimum))


def _date_normalized(value: date, earliest: date, latest: date) -> float:
    total_days = (latest - earliest).days
    if total_days == 0:
        return 1.0
    return _clamp((value - earliest).days / total_days)


def _target_score(value: int, target: int, minimum: int, maximum: int) -> float:
    span = max(maximum - minimum, 1)
    return _clamp(1 - abs(value - target) / span)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
