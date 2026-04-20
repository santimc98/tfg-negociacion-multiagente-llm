"""Simple reproducible experimental runner for TFG evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scenarios.batch import batch_result_to_dict, batch_result_to_json, run_batch_simulation
from scenarios.generator import generate_simulated_scenarios, scenario_to_dict


def run_reproducible_experiment(
    scenario_count: int = 10,
    seed: int = 42,
    max_rounds: int = 5,
    include_individual_results: bool = True,
) -> dict[str, Any]:
    """Generate scenarios, run a batch and return JSON-compatible results."""

    scenarios = generate_simulated_scenarios(count=scenario_count, seed=seed)
    batch_result = run_batch_simulation(scenarios=scenarios, max_rounds=max_rounds)
    batch_payload = batch_result_to_dict(batch_result)

    payload: dict[str, Any] = {
        "config": {
            "scenario_count": scenario_count,
            "seed": seed,
            "max_rounds": max_rounds,
        },
        "scenarios": [scenario_to_dict(scenario) for scenario in scenarios],
        "summary": batch_payload["summary"],
    }

    if include_individual_results:
        payload["runs"] = batch_payload["runs"]
    else:
        payload["runs"] = []

    return payload


def experiment_result_to_json(payload: dict[str, Any], indent: int | None = 2) -> str:
    """Serialize an experiment payload to JSON."""

    return json.dumps(payload, indent=indent, sort_keys=True)


def write_experiment_outputs(
    output_dir: Path,
    scenario_count: int = 10,
    seed: int = 42,
    max_rounds: int = 5,
) -> dict[str, Path]:
    """Run an experiment and write summary plus individual outputs."""

    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios = generate_simulated_scenarios(count=scenario_count, seed=seed)
    batch_result = run_batch_simulation(scenarios=scenarios, max_rounds=max_rounds)
    full_payload = batch_result_to_dict(batch_result)

    summary_path = output_dir / "summary.json"
    runs_path = output_dir / "runs.json"

    summary_payload = {
        "config": {
            "scenario_count": scenario_count,
            "seed": seed,
            "max_rounds": max_rounds,
        },
        "summary": full_payload["summary"],
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2, sort_keys=True), encoding="utf-8")
    runs_path.write_text(
        batch_result_to_json(batch_result, include_individual_results=True, indent=2),
        encoding="utf-8",
    )

    return {
        "summary": summary_path,
        "runs": runs_path,
    }
