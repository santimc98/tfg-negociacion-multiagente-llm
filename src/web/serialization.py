"""Serialization helpers between the web layer and the negotiation domain."""

from __future__ import annotations

from datetime import date
from typing import Any

from negotiation.metrics import calculate_metrics
from negotiation.models import (
    AgentPreferences,
    BuyerGuardrails,
    NegotiationResult,
    OfferTerms,
    PublicScenarioConstraints,
    Scenario,
    SellerGuardrails,
    TurnLog,
)
from scenarios.generator import create_basic_scenario, scenario_to_dict


def offer_terms_to_dict(terms: OfferTerms | None) -> dict[str, Any] | None:
    """Serialize offer terms for the frontend."""

    if terms is None:
        return None
    return {
        "unit_price": terms.unit_price,
        "quantity": terms.quantity,
        "delivery_deadline": terms.delivery_deadline.isoformat(),
    }


def turn_to_event(turn: TurnLog) -> dict[str, Any]:
    """Serialize a single turn into a compact event for live streaming."""

    return {
        "round_number": turn.round_number,
        "agent_role": turn.agent_role,
        "action_type": turn.action.action_type.value
        if hasattr(turn.action.action_type, "value")
        else str(turn.action.action_type),
        "offer_terms": offer_terms_to_dict(turn.action.offer_terms),
        "proposal_id": turn.action.proposal_id,
        "target_offer_id": turn.action.target_offer_id,
        "rationale": turn.action.rationale,
        "is_valid": turn.is_valid,
        "errors": list(turn.errors),
        "result_summary": turn.result_summary,
        "negotiation_state": turn.negotiation_state,
        "provider_kind": turn.provider_kind,
        "provider_model_name": turn.provider_model_name,
        "provider_latency_ms": turn.provider_latency_ms,
    }


def result_summary_event(result: NegotiationResult) -> dict[str, Any]:
    """Serialize the final outcome and metrics for the frontend."""

    metrics = calculate_metrics(result)
    agreement = result.agreement
    return {
        "stopped_reason": result.stopped_reason,
        "agreement_reached": result.agreement_reached,
        "agreement": {
            "terms": offer_terms_to_dict(agreement.terms),
            "accepted_offer_id": agreement.accepted_offer_id,
            "proposed_by": agreement.proposed_by,
            "accepted_by": agreement.accepted_by,
            "reached_at_round": agreement.reached_at_round,
            "mediated": agreement.mediated,
        }
        if agreement is not None
        else None,
        "metrics": {
            "agreement_reached": metrics.agreement_reached,
            "valid_agreement": metrics.valid_agreement,
            "rounds_used": metrics.rounds_used,
            "buyer_utility": metrics.buyer_utility,
            "seller_utility": metrics.seller_utility,
            "joint_utility": metrics.joint_utility,
            "private_feasibility_buyer": metrics.private_feasibility_buyer,
            "private_feasibility_seller": metrics.private_feasibility_seller,
            "agreement_balance_gap": metrics.agreement_balance_gap,
        },
        "providers": {
            role: {"provider_kind": desc.provider_kind, "model_name": desc.model_name}
            for role, desc in result.provider_summary.items()
        },
        "mediator": {
            "provider_kind": result.mediator_summary.provider_kind,
            "model_name": result.mediator_summary.model_name,
        }
        if result.mediator_summary is not None
        else None,
    }


def scenario_to_payload(scenario: Scenario) -> dict[str, Any]:
    """Expose a scenario as a flat dict for the configuration form."""

    return scenario_to_dict(scenario)


def scenario_from_payload(payload: dict[str, Any] | None) -> Scenario:
    """Build a Scenario from a form payload, falling back to defaults."""

    base = create_basic_scenario()
    if not payload:
        return base

    constraints = payload.get("constraints", {})
    buyer_pref = payload.get("buyer_preferences", {})
    seller_pref = payload.get("seller_preferences", {})
    buyer_guard = payload.get("buyer_guardrails", {})
    seller_guard = payload.get("seller_guardrails", {})

    def _date(value: Any, fallback: date) -> date:
        if not value:
            return fallback
        return date.fromisoformat(value)

    return Scenario(
        scenario_id=payload.get("scenario_id", base.scenario_id),
        description=payload.get("description", base.description),
        constraints=PublicScenarioConstraints(
            min_unit_price=float(constraints.get("min_unit_price", base.constraints.min_unit_price)),
            max_unit_price=float(constraints.get("max_unit_price", base.constraints.max_unit_price)),
            min_quantity=int(constraints.get("min_quantity", base.constraints.min_quantity)),
            max_quantity=int(constraints.get("max_quantity", base.constraints.max_quantity)),
            earliest_delivery_deadline=_date(
                constraints.get("earliest_delivery_deadline"),
                base.constraints.earliest_delivery_deadline,
            ),
            latest_delivery_deadline=_date(
                constraints.get("latest_delivery_deadline"),
                base.constraints.latest_delivery_deadline,
            ),
        ),
        buyer_preferences=AgentPreferences(
            target_unit_price=float(
                buyer_pref.get("target_unit_price", base.buyer_preferences.target_unit_price)
            ),
            target_quantity=int(
                buyer_pref.get("target_quantity", base.buyer_preferences.target_quantity)
            ),
            target_delivery_deadline=_date(
                buyer_pref.get("target_delivery_deadline"),
                base.buyer_preferences.target_delivery_deadline,
            ),
        ),
        seller_preferences=AgentPreferences(
            target_unit_price=float(
                seller_pref.get("target_unit_price", base.seller_preferences.target_unit_price)
            ),
            target_quantity=int(
                seller_pref.get("target_quantity", base.seller_preferences.target_quantity)
            ),
            target_delivery_deadline=_date(
                seller_pref.get("target_delivery_deadline"),
                base.seller_preferences.target_delivery_deadline,
            ),
        ),
        buyer_guardrails=BuyerGuardrails(
            buyer_max_acceptable_unit_price=float(
                buyer_guard.get(
                    "buyer_max_acceptable_unit_price",
                    base.buyer_guardrails.buyer_max_acceptable_unit_price,
                )
            ),
            buyer_min_acceptable_quantity=int(
                buyer_guard.get(
                    "buyer_min_acceptable_quantity",
                    base.buyer_guardrails.buyer_min_acceptable_quantity,
                )
            ),
            buyer_latest_acceptable_deadline=_date(
                buyer_guard.get("buyer_latest_acceptable_deadline"),
                base.buyer_guardrails.buyer_latest_acceptable_deadline,
            ),
        ),
        seller_guardrails=SellerGuardrails(
            seller_min_acceptable_unit_price=float(
                seller_guard.get(
                    "seller_min_acceptable_unit_price",
                    base.seller_guardrails.seller_min_acceptable_unit_price,
                )
            ),
            seller_min_acceptable_quantity=int(
                seller_guard.get(
                    "seller_min_acceptable_quantity",
                    base.seller_guardrails.seller_min_acceptable_quantity,
                )
            ),
            seller_earliest_acceptable_deadline=_date(
                seller_guard.get("seller_earliest_acceptable_deadline"),
                base.seller_guardrails.seller_earliest_acceptable_deadline,
            ),
        ),
    )
