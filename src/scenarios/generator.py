"""Scenario generation helpers for simulated negotiations."""

from __future__ import annotations

from datetime import date

from negotiation.models import JsonDict, Scenario


def create_basic_scenario() -> Scenario:
    """Create a deterministic scenario suitable for tests and demos."""

    return Scenario(
        scenario_id="basic-electronics-supply",
        description="Buyer negotiates a batch of electronic components with one supplier.",
        min_unit_price=80.0,
        max_unit_price=120.0,
        min_quantity=50,
        max_quantity=200,
        earliest_delivery_deadline=date(2026, 5, 10),
        latest_delivery_deadline=date(2026, 6, 10),
        buyer_target_unit_price=90.0,
        buyer_target_quantity=100,
        buyer_target_delivery_deadline=date(2026, 5, 20),
        seller_target_unit_price=110.0,
        seller_target_quantity=120,
        seller_target_delivery_deadline=date(2026, 5, 30),
    )


def scenario_to_dict(scenario: Scenario) -> JsonDict:
    """Serialize a scenario into JSON-compatible values."""

    return {
        "scenario_id": scenario.scenario_id,
        "description": scenario.description,
        "min_unit_price": scenario.min_unit_price,
        "max_unit_price": scenario.max_unit_price,
        "min_quantity": scenario.min_quantity,
        "max_quantity": scenario.max_quantity,
        "earliest_delivery_deadline": scenario.earliest_delivery_deadline.isoformat(),
        "latest_delivery_deadline": scenario.latest_delivery_deadline.isoformat(),
        "buyer_target_unit_price": scenario.buyer_target_unit_price,
        "buyer_target_quantity": scenario.buyer_target_quantity,
        "buyer_target_delivery_deadline": scenario.buyer_target_delivery_deadline.isoformat(),
        "seller_target_unit_price": scenario.seller_target_unit_price,
        "seller_target_quantity": scenario.seller_target_quantity,
        "seller_target_delivery_deadline": scenario.seller_target_delivery_deadline.isoformat(),
    }
