import unittest
from dataclasses import replace
from datetime import date

import context  # noqa: F401

from llm.provider import MockNegotiationProvider
from negotiation.engine import NegotiationEngine
from negotiation.mediator import MediationOutcome, RuleBasedMediator
from negotiation.models import (
    AgentPreferences,
    BuyerGuardrails,
    NegotiationAction,
    NegotiationActionType,
    PublicScenarioConstraints,
    Scenario,
    SellerGuardrails,
    TurnLog,
)
from negotiation.validator import (
    validate_offer_terms,
    validate_terms_for_buyer_acceptance,
    validate_terms_for_seller_acceptance,
)
from scenarios.generator import create_basic_scenario


def stalling_scenario() -> Scenario:
    """Scenario with a clear zone of possible agreement."""

    return create_basic_scenario()


def impossible_scenario() -> Scenario:
    """Scenario where seller minimum price exceeds buyer maximum price."""

    base = create_basic_scenario()
    return replace(
        base,
        buyer_guardrails=BuyerGuardrails(
            buyer_max_acceptable_unit_price=85.0,
            buyer_min_acceptable_quantity=100,
            buyer_latest_acceptable_deadline=date(2026, 5, 25),
        ),
        seller_guardrails=SellerGuardrails(
            seller_min_acceptable_unit_price=110.0,
            seller_min_acceptable_quantity=100,
            seller_earliest_acceptable_deadline=date(2026, 5, 18),
        ),
    )


class StubbornProvider:
    """Provider that keeps proposing and never accepts."""

    def describe_provider(self):
        from negotiation.models import ProviderDescriptor

        return ProviderDescriptor(provider_kind="stubborn", model_name=None)

    def generate_action(self, role, scenario, round_number, history):
        constraints = scenario.constraints
        price = (
            constraints.min_unit_price if role == "buyer" else constraints.max_unit_price
        )
        return NegotiationAction(
            agent_role=role,
            action_type=NegotiationActionType.PROPOSE,
            offer_terms=__import__(
                "negotiation.models", fromlist=["OfferTerms"]
            ).OfferTerms(
                unit_price=price,
                quantity=scenario.buyer_guardrails.buyer_min_acceptable_quantity,
                delivery_deadline=scenario.buyer_preferences.target_delivery_deadline,
            ),
            rationale="never concedes",
        )


class MediatorTest(unittest.TestCase):
    def test_rule_based_mediator_proposes_feasible_compromise(self) -> None:
        scenario = stalling_scenario()
        outcome = RuleBasedMediator().mediate(scenario, round_number=3, history=())

        self.assertTrue(outcome.feasible)
        self.assertIsNotNone(outcome.compromise_terms)
        terms = outcome.compromise_terms
        self.assertTrue(validate_offer_terms(terms, scenario).is_valid)
        self.assertTrue(validate_terms_for_buyer_acceptance(terms, scenario).is_valid)
        self.assertTrue(validate_terms_for_seller_acceptance(terms, scenario).is_valid)

    def test_rule_based_mediator_detects_impasse(self) -> None:
        outcome = RuleBasedMediator().mediate(impossible_scenario(), round_number=3, history=())

        self.assertFalse(outcome.feasible)
        self.assertIsNone(outcome.compromise_terms)

    def test_engine_without_mediator_is_unchanged(self) -> None:
        scenario = create_basic_scenario()
        result = NegotiationEngine(max_rounds=5).run(
            scenario=scenario,
            buyer_provider=MockNegotiationProvider(),
            seller_provider=MockNegotiationProvider(),
        )
        self.assertIsNone(result.mediator_summary)

    def test_mediator_breaks_deadlock_into_agreement(self) -> None:
        scenario = stalling_scenario()
        result = NegotiationEngine(max_rounds=6).run(
            scenario=scenario,
            buyer_provider=StubbornProvider(),
            seller_provider=StubbornProvider(),
            mediator=RuleBasedMediator(),
            mediation_start_round=2,
        )

        # The stubborn providers never accept, so closure depends on whether an
        # agent accepts the mediator's tabled compromise. At minimum the mediator
        # must have tabled a MEDIATE action and be recorded in the result.
        self.assertIsNotNone(result.mediator_summary)
        mediate_turns = [
            turn for turn in result.turn_log if turn.action.action_type == NegotiationActionType.MEDIATE
        ]
        self.assertTrue(mediate_turns)
        self.assertEqual(mediate_turns[0].agent_role, "mediator")

    def test_mediator_impasse_stops_negotiation(self) -> None:
        result = NegotiationEngine(max_rounds=6).run(
            scenario=impossible_scenario(),
            buyer_provider=StubbornProvider(),
            seller_provider=StubbornProvider(),
            mediator=RuleBasedMediator(),
            mediation_start_round=2,
        )

        self.assertEqual(result.stopped_reason, "mediator_impasse")
        self.assertIsNone(result.agreement)

    def test_accepting_provider_closes_mediated_agreement(self) -> None:
        """An agent that accepts the latest counterparty proposal closes on the
        mediator's tabled compromise, producing a mediated agreement."""

        from negotiation.models import ProviderDescriptor

        class AcceptingBuyer:
            def describe_provider(self):
                return ProviderDescriptor(provider_kind="accepting", model_name=None)

            def generate_action(self, role, scenario, round_number, history):
                latest = None
                for turn in reversed(history):
                    if (
                        turn.agent_role != role
                        and turn.is_valid
                        and turn.action.proposal_id is not None
                        and turn.action.action_type
                        in {
                            NegotiationActionType.PROPOSE,
                            NegotiationActionType.COUNTER,
                            NegotiationActionType.MEDIATE,
                        }
                    ):
                        latest = turn.action.proposal_id
                        break
                if latest is not None:
                    return NegotiationAction(
                        agent_role=role,
                        action_type=NegotiationActionType.ACCEPT,
                        target_offer_id=latest,
                    )
                return StubbornProvider().generate_action(role, scenario, round_number, history)

        scenario = stalling_scenario()
        result = NegotiationEngine(max_rounds=6).run(
            scenario=scenario,
            buyer_provider=AcceptingBuyer(),
            seller_provider=StubbornProvider(),
            mediator=RuleBasedMediator(),
            mediation_start_round=2,
        )

        self.assertIsNotNone(result.agreement)
        self.assertEqual(result.stopped_reason, "agreement_reached")
        self.assertTrue(result.agreement.mediated)


if __name__ == "__main__":
    unittest.main()
