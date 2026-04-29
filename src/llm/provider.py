"""Mock provider and interface for future LLM-backed agents."""

from __future__ import annotations

from negotiation.models import (
    AgentRole,
    NegotiationAction,
    NegotiationActionType,
    OfferTerms,
    ProviderDescriptor,
    Scenario,
    TurnLog,
)


class MockNegotiationProvider:
    """Deterministic provider used while LLM integration is not available."""

    def describe_provider(self) -> ProviderDescriptor:
        """Return static provider metadata for traceability."""

        return ProviderDescriptor(provider_kind="mock", model_name=None)

    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        """Generate a simple action with explicit acceptance."""

        latest_counterparty_offer_id = self._latest_counterparty_offer_id(role, history)
        if role == "buyer" and latest_counterparty_offer_id is not None and round_number >= 2:
            return NegotiationAction(
                agent_role=role,
                action_type=NegotiationActionType.ACCEPT,
                target_offer_id=latest_counterparty_offer_id,
                rationale="The seller proposal is acceptable for the simulated buyer.",
            )

        return NegotiationAction(
            agent_role=role,
            action_type=self._proposal_action_type(latest_counterparty_offer_id),
            offer_terms=self._build_offer_terms(role, scenario, round_number),
            target_offer_id=latest_counterparty_offer_id,
            rationale="Deterministic mock concession.",
        )

    def _build_offer_terms(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
    ) -> OfferTerms:
        constraints = scenario.constraints
        buyer_preferences = scenario.buyer_preferences
        seller_preferences = scenario.seller_preferences
        price_span = constraints.max_unit_price - constraints.min_unit_price
        concession = min(round_number / 4, 1.0)

        if role == "buyer":
            unit_price = constraints.min_unit_price + price_span * concession
            quantity = buyer_preferences.target_quantity
            delivery_deadline = buyer_preferences.target_delivery_deadline
        elif role == "seller":
            unit_price = constraints.max_unit_price - price_span * concession
            quantity = max(buyer_preferences.target_quantity, seller_preferences.target_quantity)
            delivery_deadline = buyer_preferences.target_delivery_deadline
        else:
            raise ValueError("role must be 'buyer' or 'seller'")

        return OfferTerms(
            unit_price=round(unit_price, 2),
            quantity=quantity,
            delivery_deadline=delivery_deadline,
        )

    def _latest_counterparty_offer_id(
        self,
        role: AgentRole,
        history: tuple[TurnLog, ...],
    ) -> str | None:
        for turn in reversed(history):
            if (
                turn.agent_role != role
                and turn.is_valid
                and turn.action.proposal_id is not None
                and turn.action.action_type
                in {NegotiationActionType.PROPOSE, NegotiationActionType.COUNTER}
            ):
                return turn.action.proposal_id
        return None

    def _proposal_action_type(self, target_offer_id: str | None) -> NegotiationActionType:
        if target_offer_id is None:
            return NegotiationActionType.PROPOSE
        return NegotiationActionType.COUNTER
