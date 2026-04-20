"""Scenario generation helpers for simulated negotiations."""

from __future__ import annotations

import random
from datetime import date, timedelta

from negotiation.models import (
    AgentPreferences,
    BuyerGuardrails,
    JsonDict,
    PublicScenarioConstraints,
    Scenario,
    SellerGuardrails,
)


def create_basic_scenario() -> Scenario:
    """Create a deterministic scenario suitable for tests and demos."""

    return Scenario(
        scenario_id="basic-electronics-supply",
        description="Buyer negotiates a batch of electronic components with one supplier.",
        constraints=PublicScenarioConstraints(
            min_unit_price=80.0,
            max_unit_price=120.0,
            min_quantity=50,
            max_quantity=200,
            earliest_delivery_deadline=date(2026, 5, 10),
            latest_delivery_deadline=date(2026, 6, 10),
        ),
        buyer_preferences=AgentPreferences(
            target_unit_price=90.0,
            target_quantity=100,
            target_delivery_deadline=date(2026, 5, 20),
        ),
        seller_preferences=AgentPreferences(
            target_unit_price=110.0,
            target_quantity=120,
            target_delivery_deadline=date(2026, 5, 30),
        ),
        buyer_guardrails=BuyerGuardrails(
            buyer_max_acceptable_unit_price=110.0,
            buyer_min_acceptable_quantity=100,
            buyer_latest_acceptable_deadline=date(2026, 5, 25),
        ),
        seller_guardrails=SellerGuardrails(
            seller_min_acceptable_unit_price=95.0,
            seller_min_acceptable_quantity=100,
            seller_earliest_acceptable_deadline=date(2026, 5, 18),
        ),
    )


def generate_simulated_scenarios(count: int, seed: int = 42) -> list[Scenario]:
    """Generate reproducible scenarios with controlled small variations."""

    if count < 0:
        raise ValueError("count must be non-negative")

    rng = random.Random(seed)
    scenarios: list[Scenario] = []
    base_date = date(2026, 5, 10)

    for index in range(count):
        min_price = round(75.0 + rng.uniform(-5.0, 8.0) + index * 0.5, 2)
        price_span = round(38.0 + rng.uniform(0.0, 12.0), 2)
        max_price = round(min_price + price_span, 2)
        min_quantity = rng.randint(40, 70)
        max_quantity = min_quantity + rng.randint(120, 170)
        earliest_deadline = base_date + timedelta(days=rng.randint(0, 5))
        latest_deadline = earliest_deadline + timedelta(days=rng.randint(25, 40))

        buyer_target_quantity = min_quantity + rng.randint(45, 70)
        seller_target_quantity = buyer_target_quantity + rng.randint(10, 35)
        seller_target_quantity = min(seller_target_quantity, max_quantity)
        buyer_target_deadline = earliest_deadline + timedelta(days=rng.randint(8, 14))
        seller_target_deadline = min(
            latest_deadline,
            buyer_target_deadline + timedelta(days=rng.randint(5, 12)),
        )
        seller_mock_price = round(max_price - price_span * 0.25, 2)

        scenarios.append(
            Scenario(
                scenario_id=f"simulated-supply-{index + 1:03d}",
                description="Controlled simulated supply negotiation scenario.",
                constraints=PublicScenarioConstraints(
                    min_unit_price=min_price,
                    max_unit_price=max_price,
                    min_quantity=min_quantity,
                    max_quantity=max_quantity,
                    earliest_delivery_deadline=earliest_deadline,
                    latest_delivery_deadline=latest_deadline,
                ),
                buyer_preferences=AgentPreferences(
                    target_unit_price=round(min_price + price_span * 0.25, 2),
                    target_quantity=buyer_target_quantity,
                    target_delivery_deadline=buyer_target_deadline,
                ),
                seller_preferences=AgentPreferences(
                    target_unit_price=seller_mock_price,
                    target_quantity=seller_target_quantity,
                    target_delivery_deadline=seller_target_deadline,
                ),
                buyer_guardrails=BuyerGuardrails(
                    buyer_max_acceptable_unit_price=round(seller_mock_price + 1.0, 2),
                    buyer_min_acceptable_quantity=buyer_target_quantity,
                    buyer_latest_acceptable_deadline=buyer_target_deadline + timedelta(days=3),
                ),
                seller_guardrails=SellerGuardrails(
                    seller_min_acceptable_unit_price=round(min_price + price_span * 0.20, 2),
                    seller_min_acceptable_quantity=min(buyer_target_quantity, seller_target_quantity),
                    seller_earliest_acceptable_deadline=buyer_target_deadline
                    - timedelta(days=2),
                ),
            )
        )

    return scenarios


def scenario_to_dict(scenario: Scenario) -> JsonDict:
    """Serialize a scenario into JSON-compatible values."""

    constraints = scenario.constraints
    buyer_preferences = scenario.buyer_preferences
    seller_preferences = scenario.seller_preferences
    buyer_guardrails = scenario.buyer_guardrails
    seller_guardrails = scenario.seller_guardrails

    return {
        "scenario_id": scenario.scenario_id,
        "description": scenario.description,
        "constraints": {
            "min_unit_price": constraints.min_unit_price,
            "max_unit_price": constraints.max_unit_price,
            "min_quantity": constraints.min_quantity,
            "max_quantity": constraints.max_quantity,
            "earliest_delivery_deadline": constraints.earliest_delivery_deadline.isoformat(),
            "latest_delivery_deadline": constraints.latest_delivery_deadline.isoformat(),
        },
        "buyer_preferences": {
            "target_unit_price": buyer_preferences.target_unit_price,
            "target_quantity": buyer_preferences.target_quantity,
            "target_delivery_deadline": buyer_preferences.target_delivery_deadline.isoformat(),
        },
        "seller_preferences": {
            "target_unit_price": seller_preferences.target_unit_price,
            "target_quantity": seller_preferences.target_quantity,
            "target_delivery_deadline": seller_preferences.target_delivery_deadline.isoformat(),
        },
        "buyer_guardrails": {
            "buyer_max_acceptable_unit_price": buyer_guardrails.buyer_max_acceptable_unit_price,
            "buyer_min_acceptable_quantity": buyer_guardrails.buyer_min_acceptable_quantity,
            "buyer_latest_acceptable_deadline": (
                buyer_guardrails.buyer_latest_acceptable_deadline.isoformat()
            ),
        },
        "seller_guardrails": {
            "seller_min_acceptable_unit_price": seller_guardrails.seller_min_acceptable_unit_price,
            "seller_min_acceptable_quantity": seller_guardrails.seller_min_acceptable_quantity,
            "seller_earliest_acceptable_deadline": (
                seller_guardrails.seller_earliest_acceptable_deadline.isoformat()
            ),
        },
    }
