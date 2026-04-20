import json
import unittest

import context  # noqa: F401

from llm.ollama_provider import ACTION_JSON_SCHEMA, OllamaConfig, OllamaNegotiationProvider
from negotiation.engine import NegotiationEngine
from negotiation.models import NegotiationActionType
from scenarios.generator import create_basic_scenario


class FakeOllamaClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.last_payload = None

    def chat(self, payload):
        self.last_payload = payload
        return {"message": {"content": self.content}}


class OllamaProviderTest(unittest.TestCase):
    def test_provider_parses_fake_ollama_response(self) -> None:
        client = FakeOllamaClient(
            json.dumps(
                {
                    "action_type": "PROPOSE",
                    "target_offer_id": None,
                    "offer_terms": {
                        "unit_price": 95.0,
                        "quantity": 100,
                        "delivery_deadline": "2026-05-20",
                    },
                    "rationale": "Initial proposal.",
                }
            )
        )
        provider = OllamaNegotiationProvider(
            config=OllamaConfig(model_name="fake-model", temperature=0.1),
            client=client,
        )

        action = provider.generate_action(
            role="buyer",
            scenario=create_basic_scenario(),
            round_number=1,
            history=(),
        )

        self.assertEqual(action.action_type, NegotiationActionType.PROPOSE)
        self.assertIsNotNone(action.offer_terms)
        self.assertEqual(client.last_payload["model"], "fake-model")
        self.assertEqual(client.last_payload["format"], ACTION_JSON_SCHEMA)
        self.assertEqual(client.last_payload["options"]["temperature"], 0.1)

    def test_provider_returns_invalid_action_for_malformed_response(self) -> None:
        provider = OllamaNegotiationProvider(client=FakeOllamaClient("{bad-json"))

        action = provider.generate_action(
            role="buyer",
            scenario=create_basic_scenario(),
            round_number=1,
            history=(),
        )

        self.assertEqual(action.agent_role, "buyer")
        self.assertEqual(action.action_type, "INVALID_LLM_OUTPUT")
        self.assertIn("Invalid Ollama provider output", action.rationale)

    def test_engine_rejects_invalid_llm_provider_output(self) -> None:
        provider = OllamaNegotiationProvider(client=FakeOllamaClient("{bad-json"))

        result = NegotiationEngine(max_rounds=2).run(
            scenario=create_basic_scenario(),
            buyer_provider=provider,
            seller_provider=provider,
        )

        self.assertFalse(result.agreement_reached)
        self.assertEqual(result.stopped_reason, "invalid_provider_output")
        self.assertEqual(len(result.turn_log), 1)
        self.assertFalse(result.turn_log[0].is_valid)
        self.assertIn("action_type must be a NegotiationActionType", result.turn_log[0].errors)


if __name__ == "__main__":
    unittest.main()
