"""Reproducible comparative evaluation for negotiation providers."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from llm.factory import ProviderKind, create_provider
from negotiation.engine import ActionProvider
from scenarios.batch import (
    BatchSimulationResult,
    batch_result_to_dict,
    run_batch_simulation,
)
from scenarios.generator import generate_simulated_scenarios, scenario_to_dict


@dataclass(frozen=True)
class ProviderExperimentConfig:
    """Provider-specific configuration recorded in an experiment."""

    provider_kind: ProviderKind
    model_name: str | None = None
    temperature: float | None = None
    history_limit: int | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class ComparisonConfig:
    """Shared configuration for a reproducible comparison."""

    seed: int = 42
    scenario_count: int = 10
    max_rounds: int = 5


@dataclass(frozen=True)
class ProviderComparisonSummary:
    """Aggregate evaluation metrics for one provider."""

    provider_kind: str
    model_name: str | None
    total_runs: int
    agreement_rate: float
    feasible_agreement_rate: float
    invalid_output_rate: float
    walk_away_rate: float
    max_rounds_rate: float
    average_rounds: float
    average_buyer_utility: float
    average_seller_utility: float
    average_balance_gap: float
    average_provider_latency_ms: float | None


@dataclass(frozen=True)
class ProviderComparisonRun:
    """Batch result plus configuration and aggregate summary."""

    config: ProviderExperimentConfig
    summary: ProviderComparisonSummary
    batch_result: BatchSimulationResult


@dataclass(frozen=True)
class ComparisonResult:
    """Full comparison output for multiple providers."""

    config: ComparisonConfig
    providers: tuple[ProviderComparisonRun, ...]


ProviderBuilder = Callable[[ProviderExperimentConfig], ActionProvider]


def compare_providers(
    config: ComparisonConfig = ComparisonConfig(),
    provider_configs: tuple[ProviderExperimentConfig, ...] | None = None,
    provider_builder: ProviderBuilder | None = None,
) -> ComparisonResult:
    """Run each provider over the exact same generated scenarios."""

    selected_configs = provider_configs or (
        ProviderExperimentConfig(provider_kind="mock"),
        ProviderExperimentConfig(
            provider_kind="ollama",
            model_name="gemma4:26b",
            temperature=0.1,
            history_limit=4,
            timeout_seconds=60.0,
        ),
    )
    build_provider = provider_builder or _build_provider
    scenarios = generate_simulated_scenarios(config.scenario_count, config.seed)
    provider_runs: list[ProviderComparisonRun] = []

    for provider_config in selected_configs:
        batch_result = run_batch_simulation(
            scenarios=scenarios,
            max_rounds=config.max_rounds,
            buyer_provider_factory=lambda provider_config=provider_config: build_provider(
                provider_config
            ),
            seller_provider_factory=lambda provider_config=provider_config: build_provider(
                provider_config
            ),
        )
        provider_runs.append(
            ProviderComparisonRun(
                config=provider_config,
                summary=build_comparison_summary(provider_config, batch_result),
                batch_result=batch_result,
            )
        )

    return ComparisonResult(config=config, providers=tuple(provider_runs))


def build_comparison_summary(
    provider_config: ProviderExperimentConfig,
    batch_result: BatchSimulationResult,
) -> ProviderComparisonSummary:
    """Calculate comparison-oriented rates and averages for one batch."""

    total_runs = len(batch_result.runs)
    denominator = total_runs or 1
    stopped_reasons = [run.result.stopped_reason for run in batch_result.runs]
    latencies = [
        turn.provider_latency_ms
        for run in batch_result.runs
        for turn in run.result.turn_log
        if turn.provider_latency_ms is not None
    ]

    return ProviderComparisonSummary(
        provider_kind=provider_config.provider_kind,
        model_name=provider_config.model_name,
        total_runs=total_runs,
        agreement_rate=batch_result.summary.agreement_rate,
        feasible_agreement_rate=batch_result.summary.feasible_agreement_rate,
        invalid_output_rate=round(stopped_reasons.count("invalid_provider_output") / denominator, 4),
        walk_away_rate=round(stopped_reasons.count("walk_away") / denominator, 4),
        max_rounds_rate=round(stopped_reasons.count("max_rounds_reached") / denominator, 4),
        average_rounds=batch_result.summary.average_rounds,
        average_buyer_utility=batch_result.summary.average_buyer_utility,
        average_seller_utility=batch_result.summary.average_seller_utility,
        average_balance_gap=batch_result.summary.average_balance_gap,
        average_provider_latency_ms=round(sum(latencies) / len(latencies), 3)
        if latencies
        else None,
    )


def comparison_result_to_dict(
    comparison: ComparisonResult,
    include_individual_results: bool = True,
) -> dict[str, Any]:
    """Convert a comparison into JSON-compatible structured data."""

    return {
        "comparison_config": asdict(comparison.config),
        "provider_results": [
            {
                "provider_config": asdict(provider_run.config),
                "summary": asdict(provider_run.summary),
                "runs": batch_result_to_dict(provider_run.batch_result)["runs"]
                if include_individual_results
                else [],
            }
            for provider_run in comparison.providers
        ],
        "scenarios": [
            scenario_to_dict(run.result.scenario)
            for run in comparison.providers[0].batch_result.runs
        ]
        if comparison.providers
        else [],
    }


def comparison_result_to_json(
    comparison: ComparisonResult,
    include_individual_results: bool = True,
    indent: int | None = 2,
) -> str:
    """Serialize a provider comparison to JSON."""

    return json.dumps(
        comparison_result_to_dict(comparison, include_individual_results),
        indent=indent,
        sort_keys=True,
    )


def write_comparison_outputs(comparison: ComparisonResult, output_dir: Path) -> dict[str, Path]:
    """Write comparative summary and individual provider results."""

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "comparison_summary.json"
    runs_path = output_dir / "comparison_runs.json"
    summary_path.write_text(
        comparison_result_to_json(comparison, include_individual_results=False),
        encoding="utf-8",
    )
    runs_path.write_text(
        comparison_result_to_json(comparison, include_individual_results=True),
        encoding="utf-8",
    )
    return {"summary": summary_path, "runs": runs_path}


def format_comparison_table(comparison: ComparisonResult) -> str:
    """Format a compact console table suitable for experiment notes."""

    headers = (
        "provider",
        "model",
        "runs",
        "agree",
        "feasible",
        "invalid",
        "walk",
        "max_rounds",
        "avg_rounds",
        "buyer_u",
        "seller_u",
        "balance",
        "latency_ms",
    )
    rows = [
        (
            summary.provider_kind,
            summary.model_name or "-",
            str(summary.total_runs),
            _rate(summary.agreement_rate),
            _rate(summary.feasible_agreement_rate),
            _rate(summary.invalid_output_rate),
            _rate(summary.walk_away_rate),
            _rate(summary.max_rounds_rate),
            f"{summary.average_rounds:.2f}",
            f"{summary.average_buyer_utility:.3f}",
            f"{summary.average_seller_utility:.3f}",
            f"{summary.average_balance_gap:.3f}",
            f"{summary.average_provider_latency_ms:.1f}"
            if summary.average_provider_latency_ms is not None
            else "-",
        )
        for summary in (provider.summary for provider in comparison.providers)
    ]
    widths = [max(len(headers[index]), *(len(row[index]) for row in rows)) for index in range(len(headers))]
    separator = "-+-".join("-" * width for width in widths)
    lines = [
        " | ".join(value.ljust(widths[index]) for index, value in enumerate(headers)),
        separator,
    ]
    lines.extend(
        " | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in rows
    )
    return "\n".join(lines)


def _build_provider(config: ProviderExperimentConfig) -> ActionProvider:
    return create_provider(
        provider_kind=config.provider_kind,
        model_name=config.model_name or "gemma4:26b",
        temperature=config.temperature if config.temperature is not None else 0.1,
        history_limit=config.history_limit if config.history_limit is not None else 4,
        timeout_seconds=config.timeout_seconds if config.timeout_seconds is not None else 60.0,
    )


def _rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> None:
    """Run a mock-versus-Ollama comparison from the command line."""

    parser = argparse.ArgumentParser(description="Compare mock and Ollama negotiation providers.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario-count", type=int, default=10)
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--model", default="gemma4:26b")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--history-limit", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--output-dir", type=Path, default=Path("experiment_outputs/comparison"))
    args = parser.parse_args()

    comparison = compare_providers(
        config=ComparisonConfig(
            seed=args.seed,
            scenario_count=args.scenario_count,
            max_rounds=args.max_rounds,
        ),
        provider_configs=(
            ProviderExperimentConfig(provider_kind="mock"),
            ProviderExperimentConfig(
                provider_kind="ollama",
                model_name=args.model,
                temperature=args.temperature,
                history_limit=args.history_limit,
                timeout_seconds=args.timeout,
            ),
        ),
    )
    paths = write_comparison_outputs(comparison, args.output_dir)
    print(format_comparison_table(comparison))
    print(f"\nSummary: {paths['summary']}")
    print(f"Individual results: {paths['runs']}")


if __name__ == "__main__":
    main()
