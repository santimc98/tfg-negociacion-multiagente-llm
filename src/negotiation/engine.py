"""Turn-based negotiation engine."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Protocol

from negotiation.models import (
    AgentRole,
    Agreement,
    NegotiationAction,
    NegotiationActionType,
    NegotiationResult,
    NegotiationState,
    OfferTerms,
    ProviderDescriptor,
    Scenario,
    TurnLog,
)
from negotiation.validator import (
    ValidationResult,
    validate_action,
    validate_agreement,
    validate_terms_for_acceptance,
)


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
        active_offer_ids: set[str] = set()
        rejected_offer_ids: set[str] = set()
        accepted_offer_ids: set[str] = set()
        active_offer_id: str | None = None
        last_state_change_reason = "initialized"
        proposal_sequence = 0
        provider_summary = {
            "buyer": self._describe_provider(buyer_provider),
            "seller": self._describe_provider(seller_provider),
        }

        for round_number in range(1, self.max_rounds + 1):
            for role, provider in (("buyer", buyer_provider), ("seller", seller_provider)):
                started_at = time.perf_counter()
                action = provider.generate_action(role, scenario, round_number, tuple(turn_log))
                provider_latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
                provider_descriptor = provider_summary[role]
                proposal_owner_by_id = {
                    proposal_id: proposal.proposer for proposal_id, proposal in proposals.items()
                }
                validation = validate_action(
                    action,
                    scenario,
                    valid_offer_ids=proposals.keys(),
                    proposal_owner_by_id=proposal_owner_by_id,
                    rejected_offer_ids=rejected_offer_ids,
                )

                if validation.is_valid and action.action_type in {
                    NegotiationActionType.PROPOSE,
                    NegotiationActionType.COUNTER,
                }:
                    proposal_sequence += 1
                    proposal_id = f"O{proposal_sequence}"
                    action = replace(action, proposal_id=proposal_id)
                    assert action.offer_terms is not None
                    proposals[proposal_id] = StoredProposal(
                        proposal_id=proposal_id,
                        proposer=role,
                        terms=action.offer_terms,
                    )
                    latest_valid_proposal_by_agent[role] = proposal_id
                    active_offer_ids.add(proposal_id)
                    active_offer_id = proposal_id
                    last_state_change_reason = f"{action.action_type.value} registered as {proposal_id}"

                if validation.is_valid and action.action_type == NegotiationActionType.ACCEPT:
                    context_validation = self._validate_accept_context(
                        action=action,
                        role=role,
                        proposals=proposals,
                        latest_valid_proposal_by_agent=latest_valid_proposal_by_agent,
                        rejected_offer_ids=rejected_offer_ids,
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
                            proposals=proposals,
                            latest_valid_proposal_by_agent=latest_valid_proposal_by_agent,
                            active_offer_ids=active_offer_ids,
                            rejected_offer_ids=rejected_offer_ids,
                            accepted_offer_ids=accepted_offer_ids,
                            active_offer_id=active_offer_id,
                            last_state_change_reason="invalid provider output",
                            provider_descriptor=provider_descriptor,
                            provider_latency_ms=provider_latency_ms,
                        )
                    )
                    return self._result(
                        scenario=scenario,
                        agreement=None,
                        turn_log=turn_log,
                        stopped_reason="invalid_provider_output",
                        provider_summary=provider_summary,
                    )

                if action.action_type == NegotiationActionType.WALK_AWAY:
                    turn_log.append(
                        self._build_turn_log(
                            round_number=round_number,
                            role=role,
                            action=action,
                            validation=validation,
                            negotiation_state="walk_away",
                            proposals=proposals,
                            latest_valid_proposal_by_agent=latest_valid_proposal_by_agent,
                            active_offer_ids=active_offer_ids,
                            rejected_offer_ids=rejected_offer_ids,
                            accepted_offer_ids=accepted_offer_ids,
                            active_offer_id=active_offer_id,
                            last_state_change_reason="walk-away action received",
                            provider_descriptor=provider_descriptor,
                            provider_latency_ms=provider_latency_ms,
                        )
                    )
                    return self._result(
                        scenario=scenario,
                        agreement=None,
                        turn_log=turn_log,
                        stopped_reason="walk_away",
                        provider_summary=provider_summary,
                    )

                if action.action_type == NegotiationActionType.REJECT:
                    assert action.target_offer_id is not None
                    rejected_offer_ids.add(action.target_offer_id)
                    active_offer_ids.discard(action.target_offer_id)
                    if active_offer_id == action.target_offer_id:
                        active_offer_id = None
                    last_state_change_reason = f"{role} rejected {action.target_offer_id}"
                    turn_log.append(
                        self._build_turn_log(
                            round_number=round_number,
                            role=role,
                            action=action,
                            validation=validation,
                            negotiation_state="running",
                            proposals=proposals,
                            latest_valid_proposal_by_agent=latest_valid_proposal_by_agent,
                            active_offer_ids=active_offer_ids,
                            rejected_offer_ids=rejected_offer_ids,
                            accepted_offer_ids=accepted_offer_ids,
                            active_offer_id=active_offer_id,
                            last_state_change_reason=last_state_change_reason,
                            provider_descriptor=provider_descriptor,
                            provider_latency_ms=provider_latency_ms,
                        )
                    )
                    continue

                if action.action_type == NegotiationActionType.ACCEPT:
                    assert action.target_offer_id is not None
                    proposal = proposals[action.target_offer_id]
                    private_acceptance_validation = validate_terms_for_acceptance(
                        role=role,
                        terms=proposal.terms,
                        scenario=scenario,
                    )
                    if not private_acceptance_validation.is_valid:
                        turn_log.append(
                            self._build_turn_log(
                                round_number=round_number,
                                role=role,
                                action=action,
                                validation=private_acceptance_validation,
                                negotiation_state="invalid_provider_output",
                                proposals=proposals,
                                latest_valid_proposal_by_agent=latest_valid_proposal_by_agent,
                                active_offer_ids=active_offer_ids,
                                rejected_offer_ids=rejected_offer_ids,
                                accepted_offer_ids=accepted_offer_ids,
                                active_offer_id=active_offer_id,
                                last_state_change_reason="private acceptance guardrail violation",
                                provider_descriptor=provider_descriptor,
                                provider_latency_ms=provider_latency_ms,
                            )
                        )
                        return self._result(
                            scenario=scenario,
                            agreement=None,
                            turn_log=turn_log,
                            stopped_reason="invalid_provider_output",
                            provider_summary=provider_summary,
                        )

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
                                proposals=proposals,
                                latest_valid_proposal_by_agent=latest_valid_proposal_by_agent,
                                active_offer_ids=active_offer_ids,
                                rejected_offer_ids=rejected_offer_ids,
                                accepted_offer_ids=accepted_offer_ids,
                                active_offer_id=active_offer_id,
                                last_state_change_reason="invalid agreement",
                                provider_descriptor=provider_descriptor,
                                provider_latency_ms=provider_latency_ms,
                            )
                        )
                        return self._result(
                            scenario=scenario,
                            agreement=None,
                            turn_log=turn_log,
                            stopped_reason="invalid_provider_output",
                            provider_summary=provider_summary,
                        )

                    accepted_offer_ids.add(proposal.proposal_id)
                    active_offer_ids.clear()
                    turn_log.append(
                        self._build_turn_log(
                            round_number=round_number,
                            role=role,
                            action=action,
                            validation=validation,
                            negotiation_state="agreement_reached",
                            proposals=proposals,
                            latest_valid_proposal_by_agent=latest_valid_proposal_by_agent,
                            active_offer_ids=active_offer_ids,
                            rejected_offer_ids=rejected_offer_ids,
                            accepted_offer_ids=accepted_offer_ids,
                            active_offer_id=None,
                            last_state_change_reason=f"{role} accepted {proposal.proposal_id}",
                            provider_descriptor=provider_descriptor,
                            provider_latency_ms=provider_latency_ms,
                        )
                    )
                    return self._result(
                        scenario=scenario,
                        agreement=agreement,
                        turn_log=turn_log,
                        stopped_reason="agreement_reached",
                        provider_summary=provider_summary,
                    )

                turn_log.append(
                    self._build_turn_log(
                        round_number=round_number,
                        role=role,
                        action=action,
                        validation=validation,
                        negotiation_state="running",
                        proposals=proposals,
                        latest_valid_proposal_by_agent=latest_valid_proposal_by_agent,
                        active_offer_ids=active_offer_ids,
                        rejected_offer_ids=rejected_offer_ids,
                        accepted_offer_ids=accepted_offer_ids,
                        active_offer_id=active_offer_id,
                        last_state_change_reason=last_state_change_reason,
                        provider_descriptor=provider_descriptor,
                        provider_latency_ms=provider_latency_ms,
                    )
                )

        return self._result(
            scenario=scenario,
            agreement=None,
            turn_log=turn_log,
            stopped_reason="max_rounds_reached",
            provider_summary=provider_summary,
        )

    def _validate_accept_context(
        self,
        action: NegotiationAction,
        role: AgentRole,
        proposals: dict[str, StoredProposal],
        latest_valid_proposal_by_agent: dict[AgentRole, str],
        rejected_offer_ids: set[str],
    ) -> ValidationResult:
        """Check that ACCEPT targets a live counterparty proposal."""

        errors: list[str] = []

        if action.target_offer_id is None:
            return ValidationResult(False, ("ACCEPT requires target_offer_id",))

        if action.target_offer_id in rejected_offer_ids:
            errors.append("ACCEPT must not target a rejected proposal")

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
        proposals: dict[str, StoredProposal],
        latest_valid_proposal_by_agent: dict[AgentRole, str],
        active_offer_ids: set[str],
        rejected_offer_ids: set[str],
        accepted_offer_ids: set[str],
        active_offer_id: str | None,
        last_state_change_reason: str,
        provider_descriptor: ProviderDescriptor,
        provider_latency_ms: float,
    ) -> TurnLog:
        target_offer_id_resolved = (
            None if action.target_offer_id is None else action.target_offer_id in proposals
        )
        return TurnLog(
            round_number=round_number,
            agent_role=role,
            action=action,
            is_valid=validation.is_valid,
            errors=validation.errors,
            negotiation_state=negotiation_state,
            target_offer_id_resolved=target_offer_id_resolved,
            result_summary=self._result_summary(action, validation, negotiation_state),
            state_after=self._state_snapshot(
                latest_valid_proposal_by_agent=latest_valid_proposal_by_agent,
                active_offer_ids=active_offer_ids,
                rejected_offer_ids=rejected_offer_ids,
                accepted_offer_ids=accepted_offer_ids,
                active_offer_id=active_offer_id,
                last_state_change_reason=last_state_change_reason,
            ),
            provider_kind=provider_descriptor.provider_kind,
            provider_model_name=provider_descriptor.model_name,
            provider_latency_ms=provider_latency_ms,
        )

    def _state_snapshot(
        self,
        latest_valid_proposal_by_agent: dict[AgentRole, str],
        active_offer_ids: set[str],
        rejected_offer_ids: set[str],
        accepted_offer_ids: set[str],
        active_offer_id: str | None,
        last_state_change_reason: str,
    ) -> NegotiationState:
        return NegotiationState(
            latest_valid_proposal_by_agent=dict(latest_valid_proposal_by_agent),
            active_offer_ids=tuple(sorted(active_offer_ids)),
            rejected_offer_ids=tuple(sorted(rejected_offer_ids)),
            accepted_offer_ids=tuple(sorted(accepted_offer_ids)),
            active_offer_id=active_offer_id,
            last_state_change_reason=last_state_change_reason,
        )

    def _result_summary(
        self,
        action: NegotiationAction,
        validation: ValidationResult,
        negotiation_state: str,
    ) -> str:
        action_type = (
            action.action_type.value
            if hasattr(action.action_type, "value")
            else str(action.action_type)
        )
        if not validation.is_valid:
            return f"{action_type} invalid: {'; '.join(validation.errors)}"
        if action.action_type in {NegotiationActionType.PROPOSE, NegotiationActionType.COUNTER}:
            return f"{action.action_type.value} accepted as valid proposal {action.proposal_id}"
        if action.action_type == NegotiationActionType.REJECT:
            return f"REJECT registered for proposal {action.target_offer_id}"
        if action.action_type == NegotiationActionType.ACCEPT:
            return f"ACCEPT closed negotiation with state {negotiation_state}"
        if action.action_type == NegotiationActionType.WALK_AWAY:
            return "WALK_AWAY closed negotiation"
        return negotiation_state

    def _result(
        self,
        scenario: Scenario,
        agreement: Agreement | None,
        turn_log: list[TurnLog],
        stopped_reason: str,
        provider_summary: dict[AgentRole, ProviderDescriptor],
    ) -> NegotiationResult:
        return NegotiationResult(
            scenario=scenario,
            max_rounds=self.max_rounds,
            agreement=agreement,
            turn_log=tuple(turn_log),
            stopped_reason=stopped_reason,
            provider_summary=provider_summary,
        )

    def _describe_provider(self, provider: ActionProvider) -> ProviderDescriptor:
        descriptor = getattr(provider, "describe_provider", None)
        if callable(descriptor):
            return descriptor()
        return ProviderDescriptor(provider_kind=provider.__class__.__name__, model_name=None)
