"""Batch simulation helpers for experimental runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from llm.provider import MockNegotiationProvider
from negotiation.engine import ActionProvider, NegotiationEngine
from negotiation.metrics import NegotiationMetrics, calculate_metrics
from negotiation.models import NegotiationResult, Scenario


ProviderFactory = Callable[[], ActionProvider]


@dataclass(frozen=True)
class BatchRun:
    """Single negotiation execution and its metrics."""

    result: NegotiationResult
    metrics: NegotiationMetrics


@dataclass(frozen=True)
class BatchSummary:
    """Aggregated metrics for a batch of negotiation runs."""

    total_runs: int
    agreement_rate: float
    feasible_agreement_rate: float
    average_rounds: float
    average_buyer_utility: float
    average_seller_utility: float
    average_balance_gap: float


@dataclass(frozen=True)
class BatchSimulationResult:
    """Full batch output with individual runs and aggregate summary."""

    runs: tuple[BatchRun, ...]
    summary: BatchSummary


def run_batch_simulation(
    scenarios: Iterable[Scenario],
    max_rounds: int = 5,
    buyer_provider_factory: ProviderFactory = MockNegotiationProvider,
    seller_provider_factory: ProviderFactory = MockNegotiationProvider,
) -> BatchSimulationResult:
    """Run one negotiation per scenario and return aggregate metrics."""

    runs: list[BatchRun] = []

    for scenario in scenarios:
        engine = NegotiationEngine(max_rounds=max_rounds)
        result = engine.run(
            scenario=scenario,
            buyer_provider=buyer_provider_factory(),
            seller_provider=seller_provider_factory(),
        )
        runs.append(BatchRun(result=result, metrics=calculate_metrics(result)))

    return BatchSimulationResult(
        runs=tuple(runs),
        summary=_build_summary(runs),
    )


def _build_summary(runs: list[BatchRun]) -> BatchSummary:
    total_runs = len(runs)
    if total_runs == 0:
        return BatchSummary(
            total_runs=0,
            agreement_rate=0.0,
            feasible_agreement_rate=0.0,
            average_rounds=0.0,
            average_buyer_utility=0.0,
            average_seller_utility=0.0,
            average_balance_gap=0.0,
        )

    agreement_count = sum(1 for run in runs if run.metrics.agreement_reached)
    feasible_count = sum(
        1
        for run in runs
        if run.metrics.valid_agreement
        and run.metrics.private_feasibility_buyer
        and run.metrics.private_feasibility_seller
    )

    return BatchSummary(
        total_runs=total_runs,
        agreement_rate=round(agreement_count / total_runs, 4),
        feasible_agreement_rate=round(feasible_count / total_runs, 4),
        average_rounds=round(_mean(run.metrics.rounds_used for run in runs), 4),
        average_buyer_utility=round(_mean(run.metrics.buyer_utility for run in runs), 4),
        average_seller_utility=round(_mean(run.metrics.seller_utility for run in runs), 4),
        average_balance_gap=round(_mean(run.metrics.agreement_balance_gap for run in runs), 4),
    )


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)
