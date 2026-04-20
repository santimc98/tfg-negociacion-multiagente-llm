"""Mock provider and interface for future LLM-backed agents."""

from __future__ import annotations

from datetime import timedelta

from negotiation.models import AgentRole, Offer, Scenario, TurnLog


class MockNegotiationProvider:
    """Deterministic provider used while LLM integration is not available."""

    def generate_offer(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> Offer:
        """Generate a simple concession-based offer."""

        del history

        price_span = scenario.max_unit_price - scenario.min_unit_price
        concession = min(round_number / 4, 1.0)

        if role == "buyer":
            unit_price = scenario.min_unit_price + price_span * concession
            quantity = scenario.buyer_target_quantity
            delivery_deadline = scenario.buyer_target_delivery_deadline
        elif role == "seller":
            unit_price = scenario.max_unit_price - price_span * concession
            quantity = max(scenario.buyer_target_quantity, scenario.seller_target_quantity)
            delivery_deadline = min(
                scenario.buyer_target_delivery_deadline,
                scenario.seller_target_delivery_deadline - timedelta(days=round_number),
            )
        else:
            raise ValueError("role must be 'buyer' or 'seller'")

        return Offer(
            agent_role=role,
            unit_price=round(unit_price, 2),
            quantity=quantity,
            delivery_deadline=delivery_deadline,
        )
