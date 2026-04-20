"""Runnable demo for the negotiation prototype."""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path
from pprint import pprint

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm.provider import MockNegotiationProvider
from negotiation.engine import NegotiationEngine
from negotiation.metrics import calculate_metrics
from scenarios.generator import create_basic_scenario


def main() -> None:
    """Run one simulated negotiation and print the result."""

    scenario = create_basic_scenario()
    provider = MockNegotiationProvider()
    engine = NegotiationEngine(max_rounds=5)

    result = engine.run(
        scenario=scenario,
        buyer_provider=provider,
        seller_provider=provider,
    )
    metrics = calculate_metrics(result)

    print("Negotiation result")
    pprint(asdict(result))
    print("\nMetrics")
    pprint(asdict(metrics))


if __name__ == "__main__":
    main()
