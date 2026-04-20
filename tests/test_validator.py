from datetime import date
import unittest

import context  # noqa: F401

from negotiation.models import Agreement, NegotiationAction, NegotiationActionType, OfferTerms
from negotiation.validator import (
    validate_action,
    validate_agreement,
    validate_offer_terms,
    validate_terms_for_buyer_acceptance,
    validate_terms_for_seller_acceptance,
)
from scenarios.generator import create_basic_scenario


class ValidatorTest(unittest.TestCase):
    def test_valid_offer_terms_pass_validation(self) -> None:
        scenario = create_basic_scenario()
        terms = OfferTerms(
            unit_price=95.0,
            quantity=100,
            delivery_deadline=date(2026, 5, 20),
        )

        result = validate_offer_terms(terms, scenario)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, ())

    def test_offer_terms_with_invalid_basic_values_fail_validation(self) -> None:
        scenario = create_basic_scenario()
        terms = OfferTerms(
            unit_price=0.0,
            quantity=0,
            delivery_deadline=date(2026, 5, 20),
        )

        result = validate_offer_terms(terms, scenario)

        self.assertFalse(result.is_valid)
        self.assertIn("unit_price must be greater than 0", result.errors)
        self.assertIn("quantity must be positive", result.errors)

    def test_offer_terms_outside_scenario_constraints_fail_validation(self) -> None:
        scenario = create_basic_scenario()
        terms = OfferTerms(
            unit_price=130.0,
            quantity=250,
            delivery_deadline=date(2026, 7, 1),
        )

        result = validate_offer_terms(terms, scenario)

        self.assertFalse(result.is_valid)
        self.assertIn("unit_price is above scenario maximum", result.errors)
        self.assertIn("quantity is above scenario maximum", result.errors)
        self.assertIn("delivery_deadline is later than scenario maximum", result.errors)

    def test_propose_requires_offer_terms(self) -> None:
        scenario = create_basic_scenario()
        action = NegotiationAction(
            agent_role="buyer",
            action_type=NegotiationActionType.PROPOSE,
        )

        result = validate_action(action, scenario)

        self.assertFalse(result.is_valid)
        self.assertIn("PROPOSE requires offer_terms", result.errors)

    def test_propose_must_not_include_target_offer_id(self) -> None:
        scenario = create_basic_scenario()
        action = NegotiationAction(
            agent_role="buyer",
            action_type=NegotiationActionType.PROPOSE,
            offer_terms=OfferTerms(
                unit_price=95.0,
                quantity=100,
                delivery_deadline=date(2026, 5, 20),
            ),
            target_offer_id="O1",
        )

        result = validate_action(action, scenario)

        self.assertFalse(result.is_valid)
        self.assertIn("PROPOSE must not include target_offer_id", result.errors)

    def test_counter_requires_target_offer_id(self) -> None:
        scenario = create_basic_scenario()
        action = NegotiationAction(
            agent_role="seller",
            action_type=NegotiationActionType.COUNTER,
            offer_terms=OfferTerms(
                unit_price=100.0,
                quantity=120,
                delivery_deadline=date(2026, 5, 20),
            ),
        )

        result = validate_action(action, scenario)

        self.assertFalse(result.is_valid)
        self.assertIn("COUNTER requires target_offer_id", result.errors)

    def test_counter_must_target_counterparty_proposal(self) -> None:
        scenario = create_basic_scenario()
        action = NegotiationAction(
            agent_role="seller",
            action_type=NegotiationActionType.COUNTER,
            offer_terms=OfferTerms(
                unit_price=100.0,
                quantity=120,
                delivery_deadline=date(2026, 5, 20),
            ),
            target_offer_id="O1",
        )

        result = validate_action(
            action,
            scenario,
            valid_offer_ids={"O1"},
            proposal_owner_by_id={"O1": "seller"},
        )

        self.assertFalse(result.is_valid)
        self.assertIn("COUNTER must target a proposal from the counterparty", result.errors)

    def test_accept_requires_valid_target_offer_id(self) -> None:
        scenario = create_basic_scenario()
        action = NegotiationAction(
            agent_role="seller",
            action_type=NegotiationActionType.ACCEPT,
            target_offer_id="missing",
        )

        result = validate_action(action, scenario, valid_offer_ids={"O1"})

        self.assertFalse(result.is_valid)
        self.assertIn("ACCEPT target_offer_id must reference a valid proposal", result.errors)

    def test_reject_requires_target_offer_id(self) -> None:
        scenario = create_basic_scenario()
        action = NegotiationAction(
            agent_role="seller",
            action_type=NegotiationActionType.REJECT,
        )

        result = validate_action(action, scenario)

        self.assertFalse(result.is_valid)
        self.assertIn("REJECT requires target_offer_id", result.errors)

    def test_reject_specific_counterparty_proposal_is_valid(self) -> None:
        scenario = create_basic_scenario()
        action = NegotiationAction(
            agent_role="seller",
            action_type=NegotiationActionType.REJECT,
            target_offer_id="O1",
        )

        result = validate_action(
            action,
            scenario,
            valid_offer_ids={"O1"},
            proposal_owner_by_id={"O1": "buyer"},
        )

        self.assertTrue(result.is_valid)

    def test_walk_away_is_generic_and_must_not_target_offer(self) -> None:
        scenario = create_basic_scenario()
        action = NegotiationAction(
            agent_role="buyer",
            action_type=NegotiationActionType.WALK_AWAY,
            target_offer_id="O1",
        )

        result = validate_action(action, scenario, valid_offer_ids={"O1"})

        self.assertFalse(result.is_valid)
        self.assertIn("WALK_AWAY must not include target_offer_id", result.errors)

    def test_buyer_acceptance_rejects_private_guardrail_violation(self) -> None:
        scenario = create_basic_scenario()
        terms = OfferTerms(
            unit_price=111.0,
            quantity=120,
            delivery_deadline=date(2026, 5, 20),
        )

        result = validate_terms_for_buyer_acceptance(terms, scenario)

        self.assertFalse(result.is_valid)
        self.assertIn("unit_price exceeds buyer maximum acceptable price", result.errors)

    def test_seller_acceptance_rejects_private_guardrail_violation(self) -> None:
        scenario = create_basic_scenario()
        terms = OfferTerms(
            unit_price=90.0,
            quantity=120,
            delivery_deadline=date(2026, 5, 20),
        )

        result = validate_terms_for_seller_acceptance(terms, scenario)

        self.assertFalse(result.is_valid)
        self.assertIn("unit_price is below seller minimum acceptable price", result.errors)

    def test_agreement_validation_does_not_use_synthetic_offer(self) -> None:
        scenario = create_basic_scenario()
        terms = OfferTerms(
            unit_price=100.0,
            quantity=100,
            delivery_deadline=date(2026, 5, 20),
        )

        result = validate_agreement(
            agreement=Agreement(
                terms=terms,
                accepted_offer_id="O1",
                proposed_by="seller",
                accepted_by="buyer",
                reached_at_round=2,
            ),
            scenario=scenario,
        )

        self.assertTrue(result.is_valid)


if __name__ == "__main__":
    unittest.main()
