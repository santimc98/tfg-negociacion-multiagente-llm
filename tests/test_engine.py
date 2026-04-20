from datetime import date
import unittest

import context  # noqa: F401

from llm.provider import MockNegotiationProvider
from negotiation.engine import NegotiationEngine
from negotiation.models import AgentRole, Offer, Scenario, TurnLog
from scenarios.generator import create_basic_scenario


class InvalidProvider:
    def generate_offer(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> Offer:
        del scenario, round_number, history
        return Offer(
            agent_role=role,
            unit_price=-1.0,
            quantity=100,
            delivery_deadline=date(2026, 5, 20),
        )


class EngineTest(unittest.TestCase):
    def test_engine_reaches_agreement_with_mock_provider(self) -> None:
        scenario = create_basic_scenario()
        provider = MockNegotiationProvider()
        engine = NegotiationEngine(max_rounds=5)

        result = engine.run(scenario, provider, provider)

        self.assertTrue(result.agreement_reached)
        self.assertIsNotNone(result.agreement)
        self.assertLessEqual(result.agreement.reached_at_round, 5)
        self.assertEqual(result.stopped_reason, "agreement_reached")
        self.assertTrue(result.turn_log)
        self.assertTrue(all(turn.is_valid for turn in result.turn_log))

    def test_engine_stops_without_agreement_when_offers_are_invalid(self) -> None:
        scenario = create_basic_scenario()
        provider = InvalidProvider()
        engine = NegotiationEngine(max_rounds=2)

        result = engine.run(scenario, provider, provider)

        self.assertFalse(result.agreement_reached)
        self.assertIsNone(result.agreement)
        self.assertEqual(result.stopped_reason, "max_rounds_reached")
        self.assertEqual(len(result.turn_log), 4)
        self.assertTrue(all(not turn.is_valid for turn in result.turn_log))


if __name__ == "__main__":
    unittest.main()
