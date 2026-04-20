"""Turn-based negotiation engine."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from negotiation.models import (
    AgentRole,
    Agreement,
    NegotiationAction,
    NegotiationActionType,
    NegotiationResult,
    OfferTerms,
    Scenario,
    TurnLog,
)
from negotiation.validator import ValidationResult, validate_action, validate_agreement


class ActionProvider(Protocol):
    """Interface expected from mock providers and future LLM providers."""

    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        """Generate the next protocol action for one role."""


@dataclass(frozen=True)
class StoredProposal:
    """Valid proposal registered by the engine."""

    proposal_id: str
    proposer: AgentRole
    terms: OfferTerms


class NegotiationEngine:
    """Run a bounded buyer-seller negotiation."""

    def __init__(self, max_rounds: int = 5) -> None:
        if max_rounds <= 0:
            raise ValueError("max_rounds must be positive")
        self.max_rounds = max_rounds

    def run(
        self,
        scenario: Scenario,
        buyer_provider: ActionProvider,
        seller_provider: ActionProvider,
    ) -> NegotiationResult:
        """Execute negotiation turns until agreement, walk-away or round limit."""

        turn_log: list[TurnLog] = []
        proposals: dict[str, StoredProposal] = {}
        latest_valid_proposal_by_agent: dict[AgentRole, str] = {}
        proposal_sequence = 0

        for round_number in range(1, self.max_rounds + 1):
            for role, provider in (("buyer", buyer_provider), ("seller", seller_provider)):
                action = provider.generate_action(role, scenario, round_number, tuple(turn_log))
                validation = validate_action(action, scenario, valid_offer_ids=proposals.keys())

                if validation.is_valid and action.action_type in {
                    NegotiationActionType.PROPOSE,
                    NegotiationActionType.COUNTER,
                }:
                    proposal_sequence += 1
                    proposal_id = f"O{proposal_sequence}"
                    action = replace(action, proposal_id=proposal_id)
                    proposals[proposal_id] = StoredProposal(
                        proposal_id=proposal_id,
                        proposer=role,
                        terms=action.offer_terms,
                    )
                    latest_valid_proposal_by_agent[role] = proposal_id

                if validation.is_valid and action.action_type == NegotiationActionType.ACCEPT:
                    context_validation = self._validate_accept_context(
                        action=action,
                        role=role,
                        proposals=proposals,
                        latest_valid_proposal_by_agent=latest_valid_proposal_by_agent,
                    )
                    if not context_validation.is_valid:
                        validation = context_validation

                if not validation.is_valid:
                    turn_log.append(
                        self._build_turn_log(
                            round_number=round_number,
                            role=role,
                            action=action,
                            validation=validation,
                            negotiation_state="invalid_provider_output",
                        )
                    )
                    return self._result(
                        scenario=scenario,
                        agreement=None,
                        turn_log=turn_log,
                        stopped_reason="invalid_provider_output",
                    )

                if action.action_type == NegotiationActionType.WALK_AWAY:
                    turn_log.append(
                        self._build_turn_log(
                            round_number=round_number,
                            role=role,
                            action=action,
                            validation=validation,
                            negotiation_state="walk_away",
                        )
                    )
                    return self._result(
                        scenario=scenario,
                        agreement=None,
                        turn_log=turn_log,
                        stopped_reason="walk_away",
                    )

                if action.action_type == NegotiationActionType.ACCEPT:
                    proposal = proposals[action.target_offer_id]
                    agreement = Agreement(
                        terms=proposal.terms,
                        accepted_offer_id=proposal.proposal_id,
                        proposed_by=proposal.proposer,
                        accepted_by=role,
                        reached_at_round=round_number,
                    )
                    agreement_validation = validate_agreement(agreement, scenario)
                    if not agreement_validation.is_valid:
                        turn_log.append(
                            self._build_turn_log(
                                round_number=round_number,
                                role=role,
                                action=action,
                                validation=agreement_validation,
                                negotiation_state="invalid_provider_output",
                            )
                        )
                        return self._result(
                            scenario=scenario,
                            agreement=None,
                            turn_log=turn_log,
                            stopped_reason="invalid_provider_output",
                        )

                    turn_log.append(
                        self._build_turn_log(
                            round_number=round_number,
                            role=role,
                            action=action,
                            validation=validation,
                            negotiation_state="agreement_reached",
                        )
                    )
                    return self._result(
                        scenario=scenario,
                        agreement=agreement,
                        turn_log=turn_log,
                        stopped_reason="agreement_reached",
                    )

                turn_log.append(
                    self._build_turn_log(
                        round_number=round_number,
                        role=role,
                        action=action,
                        validation=validation,
                        negotiation_state="running",
                    )
                )

        return self._result(
            scenario=scenario,
            agreement=None,
            turn_log=turn_log,
            stopped_reason="max_rounds_reached",
        )

    def _validate_accept_context(
        self,
        action: NegotiationAction,
        role: AgentRole,
        proposals: dict[str, StoredProposal],
        latest_valid_proposal_by_agent: dict[AgentRole, str],
    ) -> ValidationResult:
        """Check that ACCEPT targets the counterparty's latest valid proposal."""

        errors: list[str] = []

        if action.target_offer_id is None:
            return ValidationResult(False, ("ACCEPT requires target_offer_id",))

        proposal = proposals[action.target_offer_id]
        if proposal.proposer == role:
            errors.append("ACCEPT must target a proposal from the counterparty")

        expected_latest_id = latest_valid_proposal_by_agent.get(proposal.proposer)
        if action.target_offer_id != expected_latest_id:
            errors.append("ACCEPT must target the latest valid proposal from that agent")

        return ValidationResult(is_valid=not errors, errors=tuple(errors))

    def _build_turn_log(
        self,
        round_number: int,
        role: AgentRole,
        action: NegotiationAction,
        validation: ValidationResult,
        negotiation_state: str,
    ) -> TurnLog:
        return TurnLog(
            round_number=round_number,
            agent_role=role,
            action=action,
            is_valid=validation.is_valid,
            errors=validation.errors,
            negotiation_state=negotiation_state,
        )

    def _result(
        self,
        scenario: Scenario,
        agreement: Agreement | None,
        turn_log: list[TurnLog],
        stopped_reason: str,
    ) -> NegotiationResult:
        return NegotiationResult(
            scenario=scenario,
            max_rounds=self.max_rounds,
            agreement=agreement,
            turn_log=tuple(turn_log),
            stopped_reason=stopped_reason,
        )
