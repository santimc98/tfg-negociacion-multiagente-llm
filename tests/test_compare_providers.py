import json
import tempfile
import unittest
from pathlib import Path

import context  # noqa: F401

from experiments.compare_providers import (
    ComparisonConfig,
    ProviderExperimentConfig,
    compare_providers,
    comparison_result_to_dict,
    format_comparison_table,
    write_comparison_outputs,
)
from llm.provider import MockNegotiationProvider
from negotiation.models import (
    AgentRole,
    NegotiationAction,
    NegotiationActionType,
    Scenario,
    TurnLog,
)


class InvalidProvider:
    def generate_action(
        self,
        role: AgentRole,
        scenario: Scenario,
        round_number: int,
        history: tuple[TurnLog, ...],
    ) -> NegotiationAction:
        del scenario, round_number, history
        return NegotiationAction(
            agent_role=role,
            action_type="INVALID_TEST_OUTPUT",  # type: ignore[arg-type]
        )


def provider_builder(config: ProviderExperimentConfig):
    if config.model_name == "invalid-provider":
        return InvalidProvider()
    return MockNegotiationProvider()


class CompareProvidersTest(unittest.TestCase):
    def test_comparison_uses_same_scenarios_for_both_providers(self) -> None:
        comparison = compare_providers(
            config=ComparisonConfig(seed=31, scenario_count=3, max_rounds=5),
            provider_configs=(
                ProviderExperimentConfig(provider_kind="mock"),
                ProviderExperimentConfig(provider_kind="mock", model_name="second-mock"),
            ),
            provider_builder=provider_builder,
        )

        first_ids = [
            run.result.scenario.scenario_id for run in comparison.providers[0].batch_result.runs
        ]
        second_ids = [
            run.result.scenario.scenario_id for run in comparison.providers[1].batch_result.runs
        ]

        self.assertEqual(first_ids, second_ids)
        self.assertEqual(comparison.providers[0].summary.agreement_rate, 1.0)
        self.assertEqual(comparison.providers[1].summary.agreement_rate, 1.0)
        self.assertIn("provider", format_comparison_table(comparison))

    def test_invalid_output_rate_is_calculated(self) -> None:
        comparison = compare_providers(
            config=ComparisonConfig(seed=32, scenario_count=4, max_rounds=2),
            provider_configs=(
                ProviderExperimentConfig(
                    provider_kind="ollama",
                    model_name="invalid-provider",
                    temperature=0.1,
                    history_limit=4,
                    timeout_seconds=10.0,
                ),
            ),
            provider_builder=provider_builder,
        )

        summary = comparison.providers[0].summary

        self.assertEqual(summary.total_runs, 4)
        self.assertEqual(summary.invalid_output_rate, 1.0)
        self.assertEqual(summary.agreement_rate, 0.0)
        self.assertEqual(summary.walk_away_rate, 0.0)

    def test_comparison_export_records_experimental_configuration(self) -> None:
        comparison = compare_providers(
            config=ComparisonConfig(seed=33, scenario_count=2, max_rounds=3),
            provider_configs=(
                ProviderExperimentConfig(
                    provider_kind="ollama",
                    model_name="gemma4:26b",
                    temperature=0.1,
                    history_limit=3,
                    timeout_seconds=45.0,
                ),
            ),
            provider_builder=provider_builder,
        )

        payload = comparison_result_to_dict(comparison, include_individual_results=False)
        provider_config = payload["provider_results"][0]["provider_config"]

        self.assertEqual(payload["comparison_config"]["seed"], 33)
        self.assertEqual(payload["comparison_config"]["scenario_count"], 2)
        self.assertEqual(payload["comparison_config"]["max_rounds"], 3)
        self.assertEqual(provider_config["provider_kind"], "ollama")
        self.assertEqual(provider_config["model_name"], "gemma4:26b")
        self.assertEqual(provider_config["temperature"], 0.1)
        self.assertEqual(provider_config["history_limit"], 3)
        self.assertEqual(provider_config["timeout_seconds"], 45.0)
        self.assertEqual(payload["provider_results"][0]["runs"], [])

    def test_comparison_outputs_write_summary_and_individual_results(self) -> None:
        comparison = compare_providers(
            config=ComparisonConfig(seed=34, scenario_count=2, max_rounds=5),
            provider_configs=(ProviderExperimentConfig(provider_kind="mock"),),
            provider_builder=provider_builder,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_comparison_outputs(comparison, Path(tmpdir))
            summary_payload = json.loads(paths["summary"].read_text(encoding="utf-8"))
            runs_payload = json.loads(paths["runs"].read_text(encoding="utf-8"))

        self.assertEqual(summary_payload["comparison_config"]["seed"], 34)
        self.assertEqual(summary_payload["provider_results"][0]["runs"], [])
        self.assertEqual(len(runs_payload["provider_results"][0]["runs"]), 2)


if __name__ == "__main__":
    unittest.main()
