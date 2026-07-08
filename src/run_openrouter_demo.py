"""Run a simple negotiation using a cloud model through OpenRouter."""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path
from pprint import pprint

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app_config import load_env_file
from llm.factory import create_provider
from negotiation.engine import NegotiationEngine
from negotiation.metrics import calculate_metrics
from scenarios.generator import create_basic_scenario


def main() -> None:
    """Run one cloud-LLM negotiation demo through OpenRouter."""

    load_env_file()

    parser = argparse.ArgumentParser(description="Run a negotiation with OpenRouter.")
    parser.add_argument(
        "--buyer-model",
        default="deepseek/deepseek-chat",
        help="OpenRouter model slug for the buyer agent.",
    )
    parser.add_argument(
        "--seller-model",
        default="deepseek/deepseek-chat",
        help="OpenRouter model slug for the seller agent.",
    )
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Request timeout in seconds.")
    parser.add_argument("--history-limit", type=int, default=6, help="Recent turns sent to the model.")
    parser.add_argument("--max-rounds", type=int, default=6, help="Maximum negotiation rounds.")
    args = parser.parse_args()

    scenario = create_basic_scenario()
    buyer_provider = create_provider(
        provider_kind="openrouter",
        model_name=args.buyer_model,
        temperature=args.temperature,
        timeout_seconds=args.timeout,
        history_limit=args.history_limit,
    )
    seller_provider = create_provider(
        provider_kind="openrouter",
        model_name=args.seller_model,
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
