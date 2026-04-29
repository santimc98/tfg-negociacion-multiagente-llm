import json
import unittest
from datetime import date

import context  # noqa: F401

from llm.ollama_provider import ACTION_JSON_SCHEMA, OllamaConfig, OllamaNegotiationProvider
from negotiation.engine import NegotiationEngine
from negotiation.models import NegotiationAction, NegotiationActionType, OfferTerms, TurnLog
from scenarios.generator import create_basic_scenario


class FakeOllamaClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.last_payload = None

    def chat(self, payload):
        self.last_payload = payload
        return {"message": {"content": self.content}}


def make_history() -> tuple[TurnLog, ...]:
    turns = []
    for index in range(1, 7):
        turns.append(
            TurnLog(
                round_number=index,
                agent_role="buyer" if index % 2 else "seller",
                action=NegotiationAction(
                    agent_role="buyer" if index % 2 else "seller",
                    action_type=NegotiationActionType.PROPOSE,
                    offer_terms=OfferTerms(
                        unit_price=90.0 + index,
                        quantity=100 + index,
                        delivery_deadline=date(2026, 5, 20),
                    ),
                    proposal_id=f"O{index}",
                ),
                is_valid=True,
                result_summary=f"turn {index}",
            )
        )
    return tuple(turns)


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

    def test_provider_accepts_minimal_valid_response_with_null_rationale(self) -> None:
        provider = OllamaNegotiationProvider(
            client=FakeOllamaClient(
                json.dumps(
                    {
                        "action_type": "WALK_AWAY",
                        "target_offer_id": None,
                        "offer_terms": None,
                        "rationale": None,
                    }
                )
            )
        )

        action = provider.generate_action(
            role="seller",
            scenario=create_basic_scenario(),
            round_number=1,
            history=(),
        )

        self.assertEqual(action.action_type, NegotiationActionType.WALK_AWAY)
        self.assertIsNone(action.rationale)

    def test_provider_limits_history_sent_to_model(self) -> None:
        client = FakeOllamaClient(
            json.dumps(
                {
                    "action_type": "WALK_AWAY",
                    "target_offer_id": None,
                    "offer_terms": None,
                    "rationale": None,
                }
            )
        )
        provider = OllamaNegotiationProvider(
            config=OllamaConfig(history_limit=3),
            client=client,
        )

        provider.generate_action(
            role="buyer",
            scenario=create_basic_scenario(),
            round_number=4,
            history=make_history(),
        )

        user_payload = json.loads(client.last_payload["messages"][1]["content"])
        self.assertEqual(len(user_payload["history"]), 3)
        self.assertEqual(user_payload["history"][0]["proposal_id"], "O4")
        self.assertNotIn("thought", client.last_payload["messages"][0]["content"].lower())

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

    def test_provider_rejects_long_textual_response(self) -> None:
        provider = OllamaNegotiationProvider(
            client=FakeOllamaClient(
                json.dumps(
                    {
                        "action_type": "PROPOSE",
                        "target_offer_id": None,
                        "offer_terms": {
                            "unit_price": 95.0,
                            "quantity": 100,
                            "delivery_deadline": "2026-05-20",
                        },
                        "rationale": "This is a long rationale. " * 20,
                    }
                )
            )
        )

        action = provider.generate_action(
            role="buyer",
            scenario=create_basic_scenario(),
            round_number=1,
            history=(),
        )

        self.assertEqual(action.action_type, "INVALID_LLM_OUTPUT")

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
        self.assertEqual(result.turn_log[0].provider_kind, "ollama")
        self.assertGreaterEqual(result.turn_log[0].provider_latency_ms, 0.0)


if __name__ == "__main__":
    unittest.main()
