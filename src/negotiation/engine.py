"""Turn-based negotiation engine."""

from __future__ import annotations

from typing import Protocol

from negotiation.models import AgentRole, Agreement, NegotiationResult, Offer, Scenario, TurnLog
from negotiation.validator import validate_agreement, validate_offer


class OfferProvider(Protocol):
    """Interface expected from mock providers and future LLM providers."""

    def generate_offer(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> Offer:
        """Generate the next offer for one role."""


class NegotiationEngine:
    """Run a bounded buyer-seller negotiation."""

    def __init__(self, max_rounds: int = 5) -> None:
        if max_rounds <= 0:
            raise ValueError("max_rounds must be positive")
        self.max_rounds = max_rounds

    def run(
        self,
        scenario: Scenario,
        buyer_provider: OfferProvider,
        seller_provider: OfferProvider,
    ) -> NegotiationResult:
        """Execute negotiation turns until agreement or round limit."""

        turn_log: list[TurnLog] = []
        latest_valid_offers: dict[AgentRole, Offer] = {}

        for round_number in range(1, self.max_rounds + 1):
            for role, provider in (("buyer", buyer_provider), ("seller", seller_provider)):
                offer = provider.generate_offer(role, scenario, round_number, tuple(turn_log))
                validation = validate_offer(offer, scenario)
                turn_log.append(
                    TurnLog(
                        round_number=round_number,
                        agent_role=role,
                        offer=offer,
                        is_valid=validation.is_valid,
                        errors=validation.errors,
                    )
                )

                if not validation.is_valid:
                    continue

                latest_valid_offers[role] = offer
                agreement = self._build_agreement_if_compatible(
                    buyer_offer=latest_valid_offers.get("buyer"),
                    seller_offer=latest_valid_offers.get("seller"),
                    round_number=round_number,
                    scenario=scenario,
                )
                if agreement is not None:
                    return NegotiationResult(
                        scenario=scenario,
                        max_rounds=self.max_rounds,
                        agreement=agreement,
                        turn_log=tuple(turn_log),
                        stopped_reason="agreement_reached",
                    )

        return NegotiationResult(
            scenario=scenario,
            max_rounds=self.max_rounds,
            agreement=None,
            turn_log=tuple(turn_log),
            stopped_reason="max_rounds_reached",
        )

    def _build_agreement_if_compatible(
        self,
        buyer_offer: Offer | None,
        seller_offer: Offer | None,
        round_number: int,
        scenario: Scenario,
    ) -> Agreement | None:
        """Create an agreement when the latest valid offers overlap."""

        if buyer_offer is None or seller_offer is None:
            return None

        price_overlap = buyer_offer.unit_price >= seller_offer.unit_price
        quantity_overlap = seller_offer.quantity >= buyer_offer.quantity
        deadline_overlap = seller_offer.delivery_deadline <= buyer_offer.delivery_deadline

        if not (price_overlap and quantity_overlap and deadline_overlap):
            return None

        agreement = Agreement(
            unit_price=round((buyer_offer.unit_price + seller_offer.unit_price) / 2, 2),
            quantity=buyer_offer.quantity,
            delivery_deadline=seller_offer.delivery_deadline,
            reached_at_round=round_number,
        )

        if not validate_agreement(agreement, scenario).is_valid:
            return None

        return agreement
