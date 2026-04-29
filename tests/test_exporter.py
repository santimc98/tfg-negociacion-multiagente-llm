import json
import unittest

import context  # noqa: F401

from llm.ollama_provider import OllamaNegotiationProvider
from llm.provider import MockNegotiationProvider
from negotiation.engine import NegotiationEngine
from negotiation.exporter import negotiation_result_to_dict, negotiation_result_to_json
from scenarios.generator import create_basic_scenario


class FakeOllamaClient:
    def chat(self, payload):
        del payload
        return {"message": {"content": "{\"action_type\":\"WALK_AWAY\",\"target_offer_id\":null,\"offer_terms\":null,\"rationale\":null}"}}


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
        self.assertIn("providers", payload)
        self.assertEqual(payload["stopped_reason"], "agreement_reached")
        self.assertEqual(payload["turn_history"][0]["action"]["action_type"], "PROPOSE")
        self.assertIn("state_after", payload["turn_history"][0])
        self.assertIn("result_summary", payload["turn_history"][0])
        self.assertEqual(payload["providers"]["buyer"]["provider_kind"], "mock")

    def test_export_result_to_dict_is_json_compatible(self) -> None:
        scenario = create_basic_scenario()
        provider = MockNegotiationProvider()
        result = NegotiationEngine(max_rounds=5).run(scenario, provider, provider)

        exported = negotiation_result_to_dict(result)
        encoded = json.dumps(exported)

        self.assertIsInstance(encoded, str)
        self.assertEqual(exported["metrics"]["private_feasibility_buyer"], True)

    def test_export_includes_ollama_provider_metadata(self) -> None:
        scenario = create_basic_scenario()
        provider = OllamaNegotiationProvider(client=FakeOllamaClient())
        result = NegotiationEngine(max_rounds=1).run(scenario, provider, provider)

        exported = negotiation_result_to_dict(result)

        self.assertEqual(exported["providers"]["buyer"]["provider_kind"], "ollama")
        self.assertEqual(exported["providers"]["buyer"]["model_name"], "gemma4:26b")


if __name__ == "__main__":
    unittest.main()
