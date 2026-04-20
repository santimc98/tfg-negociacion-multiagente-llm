import json
import unittest

import context  # noqa: F401

from llm.provider import MockNegotiationProvider
from negotiation.engine import NegotiationEngine
from negotiation.exporter import negotiation_result_to_dict, negotiation_result_to_json
from scenarios.generator import create_basic_scenario


class ExporterTest(unittest.TestCase):
    def test_export_result_to_json_contains_required_sections(self) -> None:
        scenario = create_basic_scenario()
        provider = MockNegotiationProvider()
        result = NegotiationEngine(max_rounds=5).run(scenario, provider, provider)

        payload = json.loads(negotiation_result_to_json(result))

        self.assertIn("scenario", payload)
        self.assertIn("turn_history", payload)
        self.assertIn("agreement", payload)
        self.assertIn("metrics", payload)
        self.assertIn("stopped_reason", payload)
        self.assertEqual(payload["stopped_reason"], "agreement_reached")
        self.assertEqual(payload["turn_history"][0]["action"]["action_type"], "PROPOSE")
        self.assertIn("state_after", payload["turn_history"][0])
        self.assertIn("result_summary", payload["turn_history"][0])

    def test_export_result_to_dict_is_json_compatible(self) -> None:
        scenario = create_basic_scenario()
        provider = MockNegotiationProvider()
        result = NegotiationEngine(max_rounds=5).run(scenario, provider, provider)

        exported = negotiation_result_to_dict(result)
        encoded = json.dumps(exported)

        self.assertIsInstance(encoded, str)
        self.assertEqual(exported["metrics"]["private_feasibility_buyer"], True)


if __name__ == "__main__":
    unittest.main()
