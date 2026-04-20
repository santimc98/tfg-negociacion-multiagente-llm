import unittest

import context  # noqa: F401

from scenarios.generator import generate_simulated_scenarios


class ScenarioGeneratorTest(unittest.TestCase):
    def test_generate_simulated_scenarios_is_reproducible(self) -> None:
        first = generate_simulated_scenarios(count=4, seed=123)
        second = generate_simulated_scenarios(count=4, seed=123)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 4)

    def test_generated_scenarios_vary_prices_quantities_and_deadlines(self) -> None:
        scenarios = generate_simulated_scenarios(count=5, seed=10)

        min_prices = {scenario.constraints.min_unit_price for scenario in scenarios}
        target_quantities = {scenario.buyer_preferences.target_quantity for scenario in scenarios}
        target_deadlines = {
            scenario.buyer_preferences.target_delivery_deadline for scenario in scenarios
        }

        self.assertGreater(len(min_prices), 1)
        self.assertGreater(len(target_quantities), 1)
        self.assertGreater(len(target_deadlines), 1)

    def test_generated_scenarios_keep_guardrails_coherent(self) -> None:
        scenarios = generate_simulated_scenarios(count=5, seed=11)

        for scenario in scenarios:
            self.assertGreaterEqual(
                scenario.buyer_guardrails.buyer_max_acceptable_unit_price,
                scenario.seller_preferences.target_unit_price,
            )
            self.assertGreaterEqual(
                scenario.buyer_guardrails.buyer_min_acceptable_quantity,
                scenario.constraints.min_quantity,
            )
            self.assertLessEqual(
                scenario.buyer_guardrails.buyer_latest_acceptable_deadline,
                scenario.constraints.latest_delivery_deadline,
            )
            self.assertGreaterEqual(
                scenario.seller_guardrails.seller_min_acceptable_unit_price,
                scenario.constraints.min_unit_price,
            )
            self.assertLessEqual(
                scenario.seller_guardrails.seller_earliest_acceptable_deadline,
                scenario.constraints.latest_delivery_deadline,
            )


if __name__ == "__main__":
    unittest.main()
