"""Judge/mediator agent for the negotiation prototype.

The mediator is a neutral third participant whose job is to help the buyer and
the seller reach closure. It does **not** override agent autonomy: it only
*tables* a compromise that either agent may then accept under its own private
guardrails. As a trusted neutral, the mediator may inspect both agents' private
reservation values to compute a settlement that is acceptable to both; if no
such settlement exists (no zone of possible agreement), it declares an impasse.

This addresses the supervisor's suggestion of adding a judge/mediator role to
help finalise negotiations, and provides a measurable lever against deadlocks
where two LLM agents keep counter-offering without ever accepting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from negotiation.models import (
    OfferTerms,
    ProviderDescriptor,
    Scenario,
    TurnLog,
)
from negotiation.validator import (
    validate_offer_terms,
    validate_terms_for_buyer_acceptance,
    validate_terms_for_seller_acceptance,
)


@dataclass(frozen=True)
class MediationOutcome:
    """Result of a mediation step."""

    feasible: bool
    compromise_terms: OfferTerms | None
    rationale: str


class Mediator(Protocol):
    """Interface for any mediator implementation."""

    def describe(self) -> ProviderDescriptor:
        """Return mediator metadata for traceability."""

    def mediate(
        self,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> MediationOutcome:
        """Propose a compromise or declare an impasse."""


class RuleBasedMediator:
    """Deterministic mediator that proposes a guaranteed-feasible compromise.

    For each variable it computes the overlap between both agents' acceptance
    limits (the zone of possible agreement) and selects a balanced point inside
    it. If any variable has no overlap, no settlement can satisfy both parties
    and the mediator declares an impasse.
    """

    def describe(self) -> ProviderDescriptor:
        return ProviderDescriptor(provider_kind="mediator-rule-based", model_name=None)

    def mediate(
        self,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> MediationOutcome:
        terms = self.compromise_terms(scenario)
        if terms is None:
            return MediationOutcome(
                feasible=False,
                compromise_terms=None,
                rationale="No existe zona de posible acuerdo entre los límites privados.",
            )
        return MediationOutcome(
            feasible=True,
            compromise_terms=terms,
            rationale="Compromiso equilibrado dentro de los límites de aceptación de ambas partes.",
        )

    def compromise_terms(self, scenario: Scenario) -> OfferTerms | None:
        """Compute a settlement acceptable to both agents, or None if impossible."""

        constraints = scenario.constraints
        buyer = scenario.buyer_guardrails
        seller = scenario.seller_guardrails

        # Price overlap: seller minimum .. buyer maximum.
        price_low = seller.seller_min_acceptable_unit_price
        price_high = buyer.buyer_max_acceptable_unit_price
        if price_low > price_high:
            return None
        unit_price = round((price_low + price_high) / 2, 2)
        unit_price = _clamp_float(unit_price, constraints.min_unit_price, constraints.max_unit_price)

        # Quantity: smallest amount that satisfies both minimums.
        quantity = max(buyer.buyer_min_acceptable_quantity, seller.seller_min_acceptable_quantity)
        if quantity > constraints.max_quantity:
            return None
        quantity = int(_clamp_int(quantity, constraints.min_quantity, constraints.max_quantity))

        # Deadline overlap: seller earliest .. buyer latest.
        deadline_low = seller.seller_earliest_acceptable_deadline
        deadline_high = buyer.buyer_latest_acceptable_deadline
        if deadline_low > deadline_high:
            return None
        midpoint_days = (deadline_high - deadline_low).days // 2
        delivery_deadline = deadline_low + timedelta(days=midpoint_days)
        delivery_deadline = _clamp_date(
            delivery_deadline,
            constraints.earliest_delivery_deadline,
            constraints.latest_delivery_deadline,
        )

        terms = OfferTerms(
            unit_price=unit_price,
            quantity=quantity,
            delivery_deadline=delivery_deadline,
        )

        # Defensive check: the compromise must respect public constraints and
        # both private guardrails. Otherwise we treat it as an impasse.
        if not validate_offer_terms(terms, scenario).is_valid:
            return None
        if not validate_terms_for_buyer_acceptance(terms, scenario).is_valid:
            return None
        if not validate_terms_for_seller_acceptance(terms, scenario).is_valid:
            return None
        return terms


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _clamp_date(value: date, minimum: date, maximum: date) -> date:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value
