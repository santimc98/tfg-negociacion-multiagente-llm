from datetime import date
import unittest

import context  # noqa: F401

from negotiation.models import Offer
from negotiation.validator import validate_offer
from scenarios.generator import create_basic_scenario


class ValidatorTest(unittest.TestCase):
    def test_valid_offer_passes_validation(self) -> None:
        scenario = create_basic_scenario()
        offer = Offer(
            agent_role="buyer",
            unit_price=95.0,
            quantity=100,
            delivery_deadline=date(2026, 5, 20),
        )

        result = validate_offer(offer, scenario)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, ())

    def test_offer_with_invalid_basic_values_fails_validation(self) -> None:
        scenario = create_basic_scenario()
        offer = Offer(
            agent_role="buyer",
            unit_price=0.0,
            quantity=0,
            delivery_deadline=date(2026, 5, 20),
        )

        result = validate_offer(offer, scenario)

        self.assertFalse(result.is_valid)
        self.assertIn("unit_price must be greater than 0", result.errors)
        self.assertIn("quantity must be positive", result.errors)

    def test_offer_outside_scenario_constraints_fails_validation(self) -> None:
        scenario = create_basic_scenario()
        offer = Offer(
            agent_role="seller",
            unit_price=130.0,
            quantity=250,
            delivery_deadline=date(2026, 7, 1),
        )

        result = validate_offer(offer, scenario)

        self.assertFalse(result.is_valid)
        self.assertIn("unit_price is above scenario maximum", result.errors)
        self.assertIn("quantity is above scenario maximum", result.errors)
        self.assertIn("delivery_deadline is later than scenario maximum", result.errors)


if __name__ == "__main__":
    unittest.main()
