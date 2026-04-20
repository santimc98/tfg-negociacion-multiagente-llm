import unittest
import json

import context  # noqa: F401

from scenarios.batch import batch_result_to_json, run_batch_simulation
from scenarios.generator import create_basic_scenario, generate_simulated_scenarios


class BatchSimulationTest(unittest.TestCase):
    def test_batch_simulation_returns_aggregate_summary(self) -> None:
        scenarios = [create_basic_scenario(), create_basic_scenario()]

        batch = run_batch_simulation(scenarios, max_rounds=5)

        self.assertEqual(batch.summary.total_runs, 2)
        self.assertEqual(len(batch.runs), 2)
        self.assertEqual(batch.summary.agreement_rate, 1.0)
        self.assertEqual(batch.summary.feasible_agreement_rate, 1.0)
        self.assertGreater(batch.summary.average_rounds, 0.0)
        self.assertGreater(batch.summary.average_buyer_utility, 0.0)
        self.assertGreater(batch.summary.average_seller_utility, 0.0)
        self.assertGreaterEqual(batch.summary.average_balance_gap, 0.0)

    def test_empty_batch_returns_zero_summary(self) -> None:
        batch = run_batch_simulation([], max_rounds=5)

        self.assertEqual(batch.summary.total_runs, 0)
        self.assertEqual(batch.summary.agreement_rate, 0.0)
        self.assertEqual(batch.summary.feasible_agreement_rate, 0.0)
        self.assertEqual(batch.summary.average_rounds, 0.0)

    def test_batch_result_exports_aggregate_json(self) -> None:
        scenarios = generate_simulated_scenarios(count=3, seed=7)
        batch = run_batch_simulation(scenarios, max_rounds=5)

        payload = json.loads(batch_result_to_json(batch, include_individual_results=False))

        self.assertIn("summary", payload)
        self.assertEqual(payload["summary"]["total_runs"], 3)
        self.assertEqual(payload["runs"], [])


if __name__ == "__main__":
    unittest.main()
