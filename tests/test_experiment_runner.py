import json
import tempfile
import unittest
from pathlib import Path

import context  # noqa: F401

from experiments.runner import (
    experiment_result_to_json,
    run_reproducible_experiment,
    write_experiment_outputs,
)


class ExperimentRunnerTest(unittest.TestCase):
    def test_runner_generates_batch_payload(self) -> None:
        payload = run_reproducible_experiment(
            scenario_count=3,
            seed=21,
            max_rounds=5,
            include_individual_results=True,
        )

        self.assertEqual(payload["config"]["scenario_count"], 3)
        self.assertEqual(payload["config"]["seed"], 21)
        self.assertEqual(payload["summary"]["total_runs"], 3)
        self.assertEqual(len(payload["scenarios"]), 3)
        self.assertEqual(len(payload["runs"]), 3)

    def test_runner_payload_is_json_serializable(self) -> None:
        payload = run_reproducible_experiment(
            scenario_count=2,
            seed=22,
            max_rounds=5,
            include_individual_results=False,
        )

        decoded = json.loads(experiment_result_to_json(payload))

        self.assertEqual(decoded["summary"]["total_runs"], 2)
        self.assertEqual(decoded["runs"], [])

    def test_runner_writes_summary_and_individual_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_experiment_outputs(
                output_dir=Path(tmpdir),
                scenario_count=2,
                seed=23,
                max_rounds=5,
            )

            self.assertTrue(paths["summary"].exists())
            self.assertTrue(paths["runs"].exists())
            summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
            runs = json.loads(paths["runs"].read_text(encoding="utf-8"))
            self.assertEqual(summary["summary"]["total_runs"], 2)
            self.assertEqual(len(runs["runs"]), 2)


if __name__ == "__main__":
    unittest.main()
