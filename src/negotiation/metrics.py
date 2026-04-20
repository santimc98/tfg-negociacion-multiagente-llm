"""Basic metrics for negotiation results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from negotiation.models import Agreement, NegotiationResult, Scenario
from negotiation.validator import validate_agreement


@dataclass(frozen=True)
class NegotiationMetrics:
    """Quantitative summary of a negotiation result."""

    agreement_reached: bool
    valid_agreement: bool
    rounds_used: int
    buyer_utility: float
    seller_utility: float
    joint_utility: float


def calculate_metrics(result: NegotiationResult) -> NegotiationMetrics:
    """Calculate basic outcome and utility metrics."""

    agreement = result.agreement
    valid_agreement = agreement is not None and validate_agreement(agreement, result.scenario).is_valid
    buyer_utility = _buyer_utility(agreement, result.scenario) if valid_agreement else 0.0
    seller_utility = _seller_utility(agreement, result.scenario) if valid_agreement else 0.0

    return NegotiationMetrics(
        agreement_reached=agreement is not None,
        valid_agreement=valid_agreement,
        rounds_used=_rounds_used(result),
        buyer_utility=buyer_utility,
        seller_utility=seller_utility,
        joint_utility=round(buyer_utility + seller_utility, 4),
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

    price_score = 1 - _normalized(
        agreement.unit_price,
        scenario.min_unit_price,
        scenario.max_unit_price,
    )
    quantity_score = _target_score(
        agreement.quantity,
        scenario.buyer_target_quantity,
        scenario.min_quantity,
        scenario.max_quantity,
    )
    deadline_score = 1 - _date_normalized(
        agreement.delivery_deadline,
        scenario.earliest_delivery_deadline,
        scenario.latest_delivery_deadline,
    )

    return round((price_score + quantity_score + deadline_score) / 3, 4)


def _seller_utility(agreement: Agreement | None, scenario: Scenario) -> float:
    if agreement is None:
        return 0.0

    price_score = _normalized(
        agreement.unit_price,
        scenario.min_unit_price,
        scenario.max_unit_price,
    )
    quantity_score = _target_score(
        agreement.quantity,
        scenario.seller_target_quantity,
        scenario.min_quantity,
        scenario.max_quantity,
    )
    deadline_score = _date_normalized(
        agreement.delivery_deadline,
        scenario.earliest_delivery_deadline,
        scenario.latest_delivery_deadline,
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
