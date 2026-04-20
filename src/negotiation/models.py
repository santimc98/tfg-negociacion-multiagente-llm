"""Domain models for the negotiation prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Literal


AgentRole = Literal["buyer", "seller"]
StoppedReason = Literal[
    "agreement_reached",
    "max_rounds_reached",
    "walk_away",
    "invalid_provider_output",
]


class NegotiationActionType(str, Enum):
    """Operational actions available in the protocol."""

    PROPOSE = "PROPOSE"
    COUNTER = "COUNTER"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    WALK_AWAY = "WALK_AWAY"


@dataclass(frozen=True)
class PublicScenarioConstraints:
    """Public hard constraints known by both agents."""

    min_unit_price: float
    max_unit_price: float
    min_quantity: int
    max_quantity: int
    earliest_delivery_deadline: date
    latest_delivery_deadline: date


@dataclass(frozen=True)
class AgentPreferences:
    """Private target values used to estimate each agent utility."""

    target_unit_price: float
    target_quantity: int
    target_delivery_deadline: date


@dataclass(frozen=True)
class BuyerGuardrails:
    """Private acceptance limits for the buyer."""

    buyer_max_acceptable_unit_price: float
    buyer_min_acceptable_quantity: int
    buyer_latest_acceptable_deadline: date


@dataclass(frozen=True)
class SellerGuardrails:
    """Private acceptance limits for the seller."""

    seller_min_acceptable_unit_price: float
    seller_min_acceptable_quantity: int
    seller_earliest_acceptable_deadline: date


@dataclass(frozen=True)
class Scenario:
    """Controlled supply-chain scenario with public and private data."""

    scenario_id: str
    description: str
    constraints: PublicScenarioConstraints
    buyer_preferences: AgentPreferences
    seller_preferences: AgentPreferences
    buyer_guardrails: BuyerGuardrails
    seller_guardrails: SellerGuardrails


@dataclass(frozen=True)
class OfferTerms:
    """Negotiable terms exchanged by the agents."""

    unit_price: float
    quantity: int
    delivery_deadline: date


@dataclass(frozen=True)
class NegotiationAction:
    """Protocol action produced by a negotiation agent."""

    agent_role: AgentRole
    action_type: NegotiationActionType
    offer_terms: OfferTerms | None = None
    target_offer_id: str | None = None
    rationale: str | None = None
    proposal_id: str | None = None


@dataclass(frozen=True)
class Agreement:
    """Agreement terms explicitly accepted by one agent."""

    terms: OfferTerms
    accepted_offer_id: str
    proposed_by: AgentRole
    accepted_by: AgentRole
    reached_at_round: int


@dataclass(frozen=True)
class TurnLog:
    """Structured record of one agent turn."""

    round_number: int
    agent_role: AgentRole
    action: NegotiationAction
    is_valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    negotiation_state: str = "running"


@dataclass(frozen=True)
class NegotiationResult:
    """Final outcome of a negotiation run."""

    scenario: Scenario
    max_rounds: int
    agreement: Agreement | None
    turn_log: tuple[TurnLog, ...]
    stopped_reason: StoppedReason

    @property
    def agreement_reached(self) -> bool:
        """Return whether an agreement was reached."""

        return self.agreement is not None


JsonDict = dict[str, Any]
