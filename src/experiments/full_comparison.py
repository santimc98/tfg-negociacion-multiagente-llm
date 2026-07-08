"""Full experimental matrix: providers x mediator on/off over shared scenarios.

This produces the numeric comparison the memoria needs (one row per
configuration, columns are plain numbers), and isolates the effect of the
judge/mediator on the agreement rate by running each provider with and without
it on the exact same simulated scenarios and seed.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from experiments.compare_providers import (
    ProviderComparisonSummary,
    build_comparison_summary,
)
from llm.factory import create_provider
from negotiation.engine import ActionProvider
from negotiation.mediator import RuleBasedMediator
from scenarios.batch import run_batch_simulation
from scenarios.generator import generate_simulated_scenarios, scenario_to_dict
from experiments.compare_providers import ProviderExperimentConfig


@dataclass(frozen=True)
class ExperimentArm:
    """One experimental configuration (provider + mediator flag)."""

    label: str
    provider_kind: str
    model_name: str | None
    use_mediator: bool


@dataclass(frozen=True)
class ArmResult:
    """A finished arm with its aggregate summary."""

    arm: ExperimentArm
    summary: ProviderComparisonSummary


def default_arms(models: list[str]) -> list[ExperimentArm]:
    """Build the default matrix: mock baseline plus each model, x mediator."""

    arms: list[ExperimentArm] = [
        ExperimentArm("mock", "mock", None, False),
        ExperimentArm("mock + mediador", "mock", None, True),
    ]
    for model in models:
        arms.append(ExperimentArm(model, "openrouter", model, False))
        arms.append(ExperimentArm(f"{model} + mediador", "openrouter", model, True))
    return arms


def _provider_factory(
    arm: ExperimentArm,
    temperature: float,
    timeout: float,
    history_limit: int,
    reasoning: dict | None,
):
    def build() -> ActionProvider:
        if arm.provider_kind == "mock":
            return create_provider("mock")
        return create_provider(
            "openrouter",
            model_name=arm.model_name or "",
            temperature=temperature,
            timeout_seconds=timeout,
            history_limit=history_limit,
            reasoning=reasoning,
        )

    return build


def run_full_comparison(
    models: list[str],
    seed: int = 42,
    scenario_count: int = 5,
    max_rounds: int = 6,
    mediation_start_round: int = 3,
    temperature: float = 0.2,
    timeout: float = 120.0,
    history_limit: int = 6,
    reasoning: dict | None = None,
    arms: list[ExperimentArm] | None = None,
) -> list[ArmResult]:
    """Run every arm over the same scenarios and return their summaries."""

    scenarios = generate_simulated_scenarios(scenario_count, seed)
    selected = arms if arms is not None else default_arms(models)
    results: list[ArmResult] = []

    for arm in selected:
        factory = _provider_factory(arm, temperature, timeout, history_limit, reasoning)
        mediator_factory = RuleBasedMediator if arm.use_mediator else None
        batch_result = run_batch_simulation(
            scenarios=scenarios,
            max_rounds=max_rounds,
            buyer_provider_factory=factory,
            seller_provider_factory=factory,
            mediator_factory=mediator_factory,
            mediation_start_round=mediation_start_round,
        )
        provider_config = ProviderExperimentConfig(
            provider_kind=arm.provider_kind,
            model_name=arm.model_name,
            temperature=temperature if arm.provider_kind != "mock" else None,
            history_limit=history_limit if arm.provider_kind != "mock" else None,
            timeout_seconds=timeout if arm.provider_kind != "mock" else None,
        )
        summary = build_comparison_summary(provider_config, batch_result)
        results.append(ArmResult(arm=arm, summary=summary))

    return results


NUMERIC_COLUMNS = [
    ("arm", "configuración"),
    ("mediator", "mediador"),
    ("n", "n"),
    ("agreement_rate", "acuerdo%"),
    ("feasible_agreement_rate", "viable%"),
    ("mediated_agreement_rate", "mediado%"),
    ("invalid_output_rate", "inválida%"),
    ("walk_away_rate", "abandono%"),
    ("max_rounds_rate", "límite%"),
    ("average_rounds", "rondas"),
    ("average_buyer_utility", "util_comprador"),
    ("average_seller_utility", "util_vendedor"),
    ("average_balance_gap", "equilibrio"),
    ("average_provider_latency_ms", "latencia_ms"),
]


def arm_to_row(result: ArmResult) -> dict[str, Any]:
    """Flatten an arm result into a numeric row for tables/CSV."""

    s = result.summary
    return {
        "arm": result.arm.label,
        "mediator": "sí" if result.arm.use_mediator else "no",
        "n": s.total_runs,
        "agreement_rate": round(s.agreement_rate * 100, 1),
        "feasible_agreement_rate": round(s.feasible_agreement_rate * 100, 1),
        "mediated_agreement_rate": round(s.mediated_agreement_rate * 100, 1),
        "invalid_output_rate": round(s.invalid_output_rate * 100, 1),
        "walk_away_rate": round(s.walk_away_rate * 100, 1),
        "max_rounds_rate": round(s.max_rounds_rate * 100, 1),
        "average_rounds": s.average_rounds,
        "average_buyer_utility": s.average_buyer_utility,
        "average_seller_utility": s.average_seller_utility,
        "average_balance_gap": s.average_balance_gap,
        "average_provider_latency_ms": s.average_provider_latency_ms
        if s.average_provider_latency_ms is not None
        else "-",
    }


def format_numeric_table(results: list[ArmResult]) -> str:
    """Render a compact aligned numeric table for the console and notes."""

    rows = [arm_to_row(r) for r in results]
    headers = [label for _, label in NUMERIC_COLUMNS]
    keys = [key for key, _ in NUMERIC_COLUMNS]
    str_rows = [[str(row[key]) for key in keys] for row in rows]
    widths = [max(len(headers[i]), *(len(r[i]) for r in str_rows)) for i in range(len(headers))]
    sep = "-+-".join("-" * w for w in widths)
    lines = [" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)), sep]
    lines.extend(" | ".join(v.ljust(widths[i]) for i, v in enumerate(r)) for r in str_rows)
    return "\n".join(lines)


def write_outputs(results: list[ArmResult], output_dir: Path, config: dict[str, Any]) -> dict[str, Path]:
    """Write JSON summary, a numeric CSV and a numeric table file."""

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [arm_to_row(r) for r in results]

    json_path = output_dir / "full_comparison_summary.json"
    json_path.write_text(
        json.dumps(
            {
                "config": config,
                "results": [
                    {"arm": asdict(r.arm), "summary": asdict(r.summary)} for r in results
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    csv_path = output_dir / "full_comparison_table.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[k for k, _ in NUMERIC_COLUMNS])
        writer.writeheader()
        writer.writerows(rows)

    table_path = output_dir / "full_comparison_table.txt"
    table_path.write_text(format_numeric_table(results), encoding="utf-8")

    return {"json": json_path, "csv": csv_path, "table": table_path}


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app_config import load_env_file

    load_env_file()

    parser = argparse.ArgumentParser(description="Full provider x mediator comparison.")
    parser.add_argument(
        "--models",
        nargs="*",
        default=["deepseek/deepseek-v4-pro", "moonshotai/kimi-k2.6", "z-ai/glm-5.2"],
        help="OpenRouter model slugs to evaluate.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario-count", type=int, default=5)
    parser.add_argument("--max-rounds", type=int, default=6)
    parser.add_argument("--mediation-start-round", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--history-limit", type=int, default=6)
    parser.add_argument(
        "--reasoning",
        choices=["off", "default"],
        default="off",
        help="off disables verbose model reasoning (faster, comparable); default leaves model behaviour.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("experiment_outputs/full_comparison")
    )
    args = parser.parse_args()

    reasoning = {"enabled": False} if args.reasoning == "off" else None

    results = run_full_comparison(
        models=args.models,
        seed=args.seed,
        scenario_count=args.scenario_count,
        max_rounds=args.max_rounds,
        mediation_start_round=args.mediation_start_round,
        temperature=args.temperature,
        timeout=args.timeout,
        history_limit=args.history_limit,
        reasoning=reasoning,
    )
    config = {
        "models": args.models,
        "seed": args.seed,
        "scenario_count": args.scenario_count,
        "max_rounds": args.max_rounds,
        "mediation_start_round": args.mediation_start_round,
        "temperature": args.temperature,
        "reasoning": args.reasoning,
    }
    paths = write_outputs(results, args.output_dir, config)
    print(format_numeric_table(results))
    print(f"\nJSON:  {paths['json']}")
    print(f"CSV:   {paths['csv']}")
    print(f"Tabla: {paths['table']}")


if __name__ == "__main__":
    main()
