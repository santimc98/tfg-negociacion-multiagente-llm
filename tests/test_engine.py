from datetime import date
import unittest

import context  # noqa: F401

from llm.provider import MockNegotiationProvider
from negotiation.engine import NegotiationEngine
from negotiation.models import (
    AgentRole,
    NegotiationAction,
    NegotiationActionType,
    OfferTerms,
    Scenario,
    TurnLog,
)
from scenarios.generator import create_basic_scenario


def buyer_terms() -> OfferTerms:
    return OfferTerms(
        unit_price=110.0,
        quantity=100,
        delivery_deadline=date(2026, 6, 1),
    )


def seller_terms() -> OfferTerms:
    return OfferTerms(
        unit_price=100.0,
        quantity=150,
        delivery_deadline=date(2026, 5, 20),
    )


def buyer_private_violation_terms() -> OfferTerms:
    return OfferTerms(
        unit_price=111.0,
        quantity=120,
        delivery_deadline=date(2026, 5, 20),
    )


def seller_private_violation_terms() -> OfferTerms:
    return OfferTerms(
        unit_price=90.0,
        quantity=120,
        delivery_deadline=date(2026, 5, 20),
    )


class InvalidProvider:
    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        del scenario, round_number, history
        return NegotiationAction(
            agent_role=role,
            action_type=NegotiationActionType.PROPOSE,
        )


class WalkAwayProvider:
    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        del scenario, round_number, history
        return NegotiationAction(
            agent_role=role,
            action_type=NegotiationActionType.WALK_AWAY,
            rationale="No acceptable deal is available.",
        )


class ProposeOnlyProvider:
    def __init__(self, terms: OfferTerms) -> None:
        self.terms = terms

    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        del scenario, round_number
        latest_counterparty_offer_id = next(
            (
                turn.action.proposal_id
                for turn in reversed(history)
                if turn.agent_role != role and turn.action.proposal_id is not None
            ),
            None,
        )
        return NegotiationAction(
            agent_role=role,
            action_type=NegotiationActionType.PROPOSE
            if latest_counterparty_offer_id is None
            else NegotiationActionType.COUNTER,
            offer_terms=self.terms,
            target_offer_id=latest_counterparty_offer_id,
        )


class AcceptLatestCounterpartyProvider:
    def __init__(self, fallback_terms: OfferTerms) -> None:
        self.fallback_terms = fallback_terms

    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        del scenario
        latest_counterparty_offer_id = next(
            (
                turn.action.proposal_id
                for turn in reversed(history)
                if turn.agent_role != role and turn.action.proposal_id is not None
            ),
            None,
        )
        if latest_counterparty_offer_id is not None and round_number >= 2:
            return NegotiationAction(
                agent_role=role,
                action_type=NegotiationActionType.ACCEPT,
                target_offer_id=latest_counterparty_offer_id,
            )
        return NegotiationAction(
            agent_role=role,
            action_type=NegotiationActionType.PROPOSE
            if latest_counterparty_offer_id is None
            else NegotiationActionType.COUNTER,
            offer_terms=self.fallback_terms,
            target_offer_id=latest_counterparty_offer_id,
        )


class AlwaysAcceptLatestCounterpartyProvider:
    def __init__(self, fallback_terms: OfferTerms) -> None:
        self.fallback_terms = fallback_terms

    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        del scenario, round_number
        latest_counterparty_offer_id = next(
            (
                turn.action.proposal_id
                for turn in reversed(history)
                if turn.agent_role != role and turn.action.proposal_id is not None
            ),
            None,
        )
        if latest_counterparty_offer_id is not None:
            return NegotiationAction(
                agent_role=role,
                action_type=NegotiationActionType.ACCEPT,
                target_offer_id=latest_counterparty_offer_id,
            )
        return NegotiationAction(
            agent_role=role,
            action_type=NegotiationActionType.PROPOSE,
            offer_terms=self.fallback_terms,
        )


class EngineTest(unittest.TestCase):
    def test_engine_reaches_agreement_only_with_explicit_acceptance(self) -> None:
        scenario = create_basic_scenario()
        provider = MockNegotiationProvider()
        engine = NegotiationEngine(max_rounds=5)

        result = engine.run(scenario, provider, provider)

        self.assertTrue(result.agreement_reached)
        self.assertIsNotNone(result.agreement)
        self.assertEqual(result.stopped_reason, "agreement_reached")
        self.assertEqual(result.agreement.accepted_by, "buyer")
        self.assertEqual(result.agreement.proposed_by, "seller")
        accepted_offer = next(
            turn.action
            for turn in result.turn_log
            if turn.action.proposal_id == result.agreement.accepted_offer_id
        )
        self.assertEqual(result.agreement.terms, accepted_offer.offer_terms)
        self.assertEqual(result.turn_log[-1].action.action_type, NegotiationActionType.ACCEPT)
        self.assertEqual(result.turn_log[-1].negotiation_state, "agreement_reached")
        self.assertIsNotNone(result.turn_log[-1].state_after)
        self.assertEqual(result.turn_log[-1].state_after.accepted_offer_ids, ("O2",))
        self.assertEqual(result.turn_log[-1].state_after.active_offer_ids, ())

    def test_overlapping_offers_do_not_create_automatic_agreement(self) -> None:
        scenario = create_basic_scenario()
        engine = NegotiationEngine(max_rounds=1)

        result = engine.run(
            scenario,
            buyer_provider=ProposeOnlyProvider(buyer_terms()),
            seller_provider=ProposeOnlyProvider(seller_terms()),
        )

        self.assertFalse(result.agreement_reached)
        self.assertIsNone(result.agreement)
        self.assertEqual(result.stopped_reason, "max_rounds_reached")
        self.assertEqual(len(result.turn_log), 2)
        self.assertTrue(all(turn.is_valid for turn in result.turn_log))

    def test_explicit_acceptance_uses_exact_target_terms(self) -> None:
        scenario = create_basic_scenario()
        engine = NegotiationEngine(max_rounds=2)

        result = engine.run(
            scenario,
            buyer_provider=AcceptLatestCounterpartyProvider(buyer_terms()),
            seller_provider=ProposeOnlyProvider(seller_terms()),
        )

        self.assertTrue(result.agreement_reached)
        self.assertIsNotNone(result.agreement)
        self.assertEqual(result.agreement.terms, seller_terms())
        self.assertEqual(result.agreement.accepted_offer_id, "O2")

    def test_buyer_accept_is_rejected_when_private_guardrails_are_violated(self) -> None:
        scenario = create_basic_scenario()
        engine = NegotiationEngine(max_rounds=2)

        result = engine.run(
            scenario,
            buyer_provider=AcceptLatestCounterpartyProvider(buyer_terms()),
            seller_provider=ProposeOnlyProvider(buyer_private_violation_terms()),
        )

        self.assertFalse(result.agreement_reached)
        self.assertIsNone(result.agreement)
        self.assertEqual(result.stopped_reason, "invalid_provider_output")
        self.assertEqual(result.turn_log[-1].action.action_type, NegotiationActionType.ACCEPT)
        self.assertFalse(result.turn_log[-1].is_valid)
        self.assertIn(
            "unit_price exceeds buyer maximum acceptable price",
            result.turn_log[-1].errors,
        )

    def test_seller_accept_is_rejected_when_private_guardrails_are_violated(self) -> None:
        scenario = create_basic_scenario()
        engine = NegotiationEngine(max_rounds=2)

        result = engine.run(
            scenario,
            buyer_provider=ProposeOnlyProvider(seller_private_violation_terms()),
            seller_provider=AlwaysAcceptLatestCounterpartyProvider(seller_terms()),
        )

        self.assertFalse(result.agreement_reached)
        self.assertIsNone(result.agreement)
        self.assertEqual(result.stopped_reason, "invalid_provider_output")
        self.assertEqual(result.turn_log[-1].action.action_type, NegotiationActionType.ACCEPT)
        self.assertFalse(result.turn_log[-1].is_valid)
        self.assertIn(
            "unit_price is below seller minimum acceptable price",
            result.turn_log[-1].errors,
        )

    def test_valid_agreement_satisfies_public_and_private_constraints(self) -> None:
        scenario = create_basic_scenario()
        engine = NegotiationEngine(max_rounds=2)

        result = engine.run(
            scenario,
            buyer_provider=AcceptLatestCounterpartyProvider(buyer_terms()),
            seller_provider=ProposeOnlyProvider(seller_terms()),
        )

        self.assertTrue(result.agreement_reached)
        self.assertIsNotNone(result.agreement)
        self.assertEqual(result.stopped_reason, "agreement_reached")
        self.assertEqual(result.agreement.terms, seller_terms())

    def test_engine_stops_on_invalid_provider_output(self) -> None:
        scenario = create_basic_scenario()
        provider = InvalidProvider()
        engine = NegotiationEngine(max_rounds=2)

        result = engine.run(scenario, provider, provider)

        self.assertFalse(result.agreement_reached)
        self.assertIsNone(result.agreement)
        self.assertEqual(result.stopped_reason, "invalid_provider_output")
        self.assertEqual(len(result.turn_log), 1)
        self.assertFalse(result.turn_log[0].is_valid)
        self.assertIn("PROPOSE requires offer_terms", result.turn_log[0].errors)

    def test_engine_stops_on_walk_away(self) -> None:
        scenario = create_basic_scenario()
        engine = NegotiationEngine(max_rounds=5)

        result = engine.run(
            scenario,
            buyer_provider=WalkAwayProvider(),
            seller_provider=ProposeOnlyProvider(seller_terms()),
        )

        self.assertFalse(result.agreement_reached)
        self.assertIsNone(result.agreement)
        self.assertEqual(result.stopped_reason, "walk_away")
        self.assertEqual(len(result.turn_log), 1)
        self.assertEqual(result.turn_log[0].negotiation_state, "walk_away")


if __name__ == "__main__":
    unittest.main()
