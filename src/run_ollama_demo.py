"""Run a simple negotiation using a local Ollama model."""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path
from pprint import pprint

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm.factory import create_provider
from negotiation.engine import NegotiationEngine
from negotiation.metrics import calculate_metrics
from scenarios.generator import create_basic_scenario


def main() -> None:
    """Run one local-LLM negotiation demo."""

    parser = argparse.ArgumentParser(description="Run a negotiation with Ollama.")
    parser.add_argument("--model", default="gemma4:26b", help="Ollama model name.")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama base URL.")
    parser.add_argument("--temperature", type=float, default=0.1, help="Sampling temperature.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Request timeout in seconds.")
    parser.add_argument("--history-limit", type=int, default=4, help="Recent turns sent to the model.")
    parser.add_argument("--max-rounds", type=int, default=5, help="Maximum negotiation rounds.")
    args = parser.parse_args()

    scenario = create_basic_scenario()
    buyer_provider = create_provider(
        provider_kind="ollama",
        model_name=args.model,
        base_url=args.base_url,
        temperature=args.temperature,
        timeout_seconds=args.timeout,
        history_limit=args.history_limit,
    )
    seller_provider = create_provider(
        provider_kind="ollama",
        model_name=args.model,
        base_url=args.base_url,
        temperature=args.temperature,
        timeout_seconds=args.timeout,
        history_limit=args.history_limit,
    )

    result = NegotiationEngine(max_rounds=args.max_rounds).run(
        scenario=scenario,
        buyer_provider=buyer_provider,
        seller_provider=seller_provider,
    )

    print("Negotiation result")
    pprint(asdict(result))
    print("\nMetrics")
    pprint(asdict(calculate_metrics(result)))


if __name__ == "__main__":
    main()
