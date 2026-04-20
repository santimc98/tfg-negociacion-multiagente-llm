"""Scenario generation helpers for simulated negotiations."""

from __future__ import annotations

from datetime import date

from negotiation.models import AgentPreferences, JsonDict, PublicScenarioConstraints, Scenario


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
    )


def scenario_to_dict(scenario: Scenario) -> JsonDict:
    """Serialize a scenario into JSON-compatible values."""

    constraints = scenario.constraints
    buyer_preferences = scenario.buyer_preferences
    seller_preferences = scenario.seller_preferences

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
    }
