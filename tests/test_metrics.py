from datetime import date
import unittest

import context  # noqa: F401

from negotiation.metrics import calculate_metrics
from negotiation.models import Agreement, NegotiationResult
from scenarios.generator import create_basic_scenario


class MetricsTest(unittest.TestCase):
    def test_metrics_for_valid_agreement(self) -> None:
        scenario = create_basic_scenario()
        agreement = Agreement(
            unit_price=100.0,
            quantity=100,
            delivery_deadline=date(2026, 5, 20),
            reached_at_round=3,
        )
        result = NegotiationResult(
            scenario=scenario,
            max_rounds=5,
            agreement=agreement,
            turn_log=(),
            stopped_reason="agreement_reached",
        )

        metrics = calculate_metrics(result)

        self.assertTrue(metrics.agreement_reached)
        self.assertTrue(metrics.valid_agreement)
        self.assertEqual(metrics.rounds_used, 3)
        self.assertGreaterEqual(metrics.buyer_utility, 0.0)
        self.assertLessEqual(metrics.buyer_utility, 1.0)
        self.assertGreaterEqual(metrics.seller_utility, 0.0)
        self.assertLessEqual(metrics.seller_utility, 1.0)
        self.assertEqual(
            metrics.joint_utility,
            round(metrics.buyer_utility + metrics.seller_utility, 4),
        )

    def test_metrics_without_agreement_are_zero_for_utilities(self) -> None:
        scenario = create_basic_scenario()
        result = NegotiationResult(
            scenario=scenario,
            max_rounds=5,
            agreement=None,
            turn_log=(),
            stopped_reason="max_rounds_reached",
        )

        metrics = calculate_metrics(result)

        self.assertFalse(metrics.agreement_reached)
        self.assertFalse(metrics.valid_agreement)
        self.assertEqual(metrics.rounds_used, 0)
        self.assertEqual(metrics.buyer_utility, 0.0)
        self.assertEqual(metrics.seller_utility, 0.0)
        self.assertEqual(metrics.joint_utility, 0.0)


if __name__ == "__main__":
    unittest.main()
