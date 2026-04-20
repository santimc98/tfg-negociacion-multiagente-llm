from datetime import date
import unittest

import context  # noqa: F401

from negotiation.engine import NegotiationEngine
from negotiation.models import (
    AgentRole,
    NegotiationAction,
    NegotiationActionType,
    OfferTerms,
    Scenario,
    TurnLog,
)
from scenarios.generator import create_basic_scenario


def valid_terms() -> OfferTerms:
    return OfferTerms(
        unit_price=100.0,
        quantity=120,
        delivery_deadline=date(2026, 5, 20),
    )


class ProposeThenRejectBuyer:
    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        del role, scenario, round_number, history
        return NegotiationAction(
            agent_role="buyer",
            action_type=NegotiationActionType.PROPOSE,
            offer_terms=valid_terms(),
        )


class RejectLatestSeller:
    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        del scenario, round_number
        latest_counterparty_offer_id = next(
            (
                turn.action.proposal_id
                for turn in reversed(history)
                if turn.agent_role != role and turn.action.proposal_id is not None
            ),
            None,
        )
        if latest_counterparty_offer_id is None:
            return NegotiationAction(
                agent_role=role,
                action_type=NegotiationActionType.WALK_AWAY,
            )
        return NegotiationAction(
            agent_role=role,
            action_type=NegotiationActionType.REJECT,
            target_offer_id=latest_counterparty_offer_id,
        )


class NegotiationStateTest(unittest.TestCase):
    def test_state_tracks_latest_valid_proposal_and_active_offer(self) -> None:
        scenario = create_basic_scenario()
        result = NegotiationEngine(max_rounds=1).run(
            scenario,
            buyer_provider=ProposeThenRejectBuyer(),
            seller_provider=RejectLatestSeller(),
        )

        first_turn_state = result.turn_log[0].state_after

        self.assertIsNotNone(first_turn_state)
        self.assertEqual(first_turn_state.latest_valid_proposal_by_agent["buyer"], "O1")
        self.assertEqual(first_turn_state.active_offer_id, "O1")
        self.assertEqual(result.turn_log[0].target_offer_id_resolved, None)
        self.assertIn("valid proposal O1", result.turn_log[0].result_summary)

    def test_state_tracks_rejected_proposals(self) -> None:
        scenario = create_basic_scenario()
        result = NegotiationEngine(max_rounds=1).run(
            scenario,
            buyer_provider=ProposeThenRejectBuyer(),
            seller_provider=RejectLatestSeller(),
        )

        second_turn_state = result.turn_log[1].state_after

        self.assertIsNotNone(second_turn_state)
        self.assertEqual(second_turn_state.rejected_offer_ids, ("O1",))
        self.assertIsNone(second_turn_state.active_offer_id)
        self.assertEqual(result.turn_log[1].target_offer_id_resolved, True)
        self.assertEqual(result.turn_log[1].result_summary, "REJECT registered for proposal O1")
        self.assertIn("seller rejected O1", second_turn_state.last_state_change_reason)


if __name__ == "__main__":
    unittest.main()
