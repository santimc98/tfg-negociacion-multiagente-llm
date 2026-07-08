import json
import unittest
from datetime import date

import context  # noqa: F401

from llm.factory import create_provider
from llm.openrouter_provider import (
    OpenRouterConfig,
    OpenRouterNegotiationProvider,
    OpenRouterProviderError,
    _strip_json_fences,
)
from negotiation.engine import NegotiationEngine
from negotiation.models import NegotiationAction, NegotiationActionType, OfferTerms, TurnLog
from scenarios.generator import create_basic_scenario


class FakeOpenRouterClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.last_payload = None

    def chat(self, payload):
        self.last_payload = payload
        return {"choices": [{"message": {"content": self.content}}]}


class RaisingOpenRouterClient:
    def chat(self, payload):
        raise OpenRouterProviderError("boom")


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


class OpenRouterProviderTest(unittest.TestCase):
    def test_provider_parses_openai_shaped_response(self) -> None:
        client = FakeOpenRouterClient(
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
        provider = OpenRouterNegotiationProvider(
            config=OpenRouterConfig(model_name="deepseek/deepseek-chat", temperature=0.2),
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
        self.assertEqual(client.last_payload["model"], "deepseek/deepseek-chat")
        self.assertEqual(client.last_payload["response_format"], {"type": "json_object"})
        self.assertEqual(client.last_payload["temperature"], 0.2)

    def test_provider_strips_markdown_code_fences(self) -> None:
        fenced = "```json\n" + json.dumps(
            {
                "action_type": "WALK_AWAY",
                "target_offer_id": None,
                "offer_terms": None,
                "rationale": None,
            }
        ) + "\n```"
        provider = OpenRouterNegotiationProvider(client=FakeOpenRouterClient(fenced))

        action = provider.generate_action(
            role="seller",
            scenario=create_basic_scenario(),
            round_number=1,
            history=(),
        )

        self.assertEqual(action.action_type, NegotiationActionType.WALK_AWAY)

    def test_provider_limits_history_sent_to_model(self) -> None:
        client = FakeOpenRouterClient(
            json.dumps(
                {
                    "action_type": "WALK_AWAY",
                    "target_offer_id": None,
                    "offer_terms": None,
                    "rationale": None,
                }
            )
        )
        provider = OpenRouterNegotiationProvider(
            config=OpenRouterConfig(history_limit=3),
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

    def test_provider_returns_invalid_action_for_malformed_response(self) -> None:
        provider = OpenRouterNegotiationProvider(client=FakeOpenRouterClient("{bad-json"))

        action = provider.generate_action(
            role="buyer",
            scenario=create_basic_scenario(),
            round_number=1,
            history=(),
        )

        self.assertEqual(action.action_type, "INVALID_LLM_OUTPUT")
        self.assertIn("Invalid OpenRouter provider output", action.rationale)

    def test_provider_returns_invalid_action_when_client_raises(self) -> None:
        provider = OpenRouterNegotiationProvider(client=RaisingOpenRouterClient())

        action = provider.generate_action(
            role="buyer",
            scenario=create_basic_scenario(),
            round_number=1,
            history=(),
        )

        self.assertEqual(action.action_type, "INVALID_LLM_OUTPUT")

    def test_missing_api_key_yields_invalid_action(self) -> None:
        # No client injected and no api key -> the default HTTP client raises,
        # which the provider converts into a controlled invalid action.
        provider = OpenRouterNegotiationProvider(
            config=OpenRouterConfig(api_key=None, model_name="deepseek/deepseek-chat")
        )
        # Ensure the environment variable is not set for this check.
        import os

        previous = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            action = provider.generate_action(
                role="buyer",
                scenario=create_basic_scenario(),
                round_number=1,
                history=(),
            )
        finally:
            if previous is not None:
                os.environ["OPENROUTER_API_KEY"] = previous

        self.assertEqual(action.action_type, "INVALID_LLM_OUTPUT")
        self.assertIn("API key", action.rationale)

    def test_factory_creates_openrouter_provider(self) -> None:
        provider = create_provider(
            "openrouter",
            model_name="moonshotai/kimi-k2",
            api_key="test-key",
        )

        self.assertIsInstance(provider, OpenRouterNegotiationProvider)
        self.assertEqual(provider.describe_provider().model_name, "moonshotai/kimi-k2")

    def test_engine_rejects_invalid_openrouter_output(self) -> None:
        provider = OpenRouterNegotiationProvider(client=FakeOpenRouterClient("{bad-json"))

        result = NegotiationEngine(max_rounds=2).run(
            scenario=create_basic_scenario(),
            buyer_provider=provider,
            seller_provider=provider,
        )

        self.assertFalse(result.agreement_reached)
        self.assertEqual(result.stopped_reason, "invalid_provider_output")
        self.assertEqual(result.turn_log[0].provider_kind, "openrouter")

    def test_strip_json_fences_plain_text(self) -> None:
        self.assertEqual(_strip_json_fences('{"a": 1}'), '{"a": 1}')


if __name__ == "__main__":
    unittest.main()
