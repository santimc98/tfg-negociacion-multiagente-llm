from datetime import date
import unittest

import context  # noqa: F401

from llm.action_parser import LLMActionParseError, parse_llm_action_response
from negotiation.models import NegotiationActionType


class ActionParserTest(unittest.TestCase):
    def test_parse_valid_structured_action(self) -> None:
        action = parse_llm_action_response(
            {
                "action_type": "COUNTER",
                "target_offer_id": "O1",
                "offer_terms": {
                    "unit_price": 101.5,
                    "quantity": 120,
                    "delivery_deadline": "2026-05-20",
                },
                "rationale": "Balanced counteroffer.",
            },
            role="seller",
        )

        self.assertEqual(action.agent_role, "seller")
        self.assertEqual(action.action_type, NegotiationActionType.COUNTER)
        self.assertEqual(action.target_offer_id, "O1")
        self.assertIsNotNone(action.offer_terms)
        self.assertEqual(action.offer_terms.delivery_deadline, date(2026, 5, 20))
        self.assertEqual(action.rationale, "Balanced counteroffer.")

    def test_parse_valid_json_string(self) -> None:
        action = parse_llm_action_response(
            """
            {
              "action_type": "ACCEPT",
              "target_offer_id": "O2",
              "offer_terms": null,
              "rationale": "Acceptable terms."
            }
            """,
            role="buyer",
        )

        self.assertEqual(action.action_type, NegotiationActionType.ACCEPT)
        self.assertEqual(action.target_offer_id, "O2")
        self.assertIsNone(action.offer_terms)

    def test_malformed_json_raises_controlled_error(self) -> None:
        with self.assertRaises(LLMActionParseError):
            parse_llm_action_response("{not-json", role="buyer")

    def test_invalid_offer_terms_type_raises_controlled_error(self) -> None:
        with self.assertRaises(LLMActionParseError):
            parse_llm_action_response(
                {
                    "action_type": "PROPOSE",
                    "offer_terms": {
                        "unit_price": "100",
                        "quantity": 120,
                        "delivery_deadline": "2026-05-20",
                    },
                },
                role="buyer",
            )


if __name__ == "__main__":
    unittest.main()
