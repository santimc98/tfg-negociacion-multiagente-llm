"""Structured JSON export for negotiation results."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date
from enum import Enum
from typing import Any

from negotiation.metrics import calculate_metrics
from negotiation.models import NegotiationResult
from scenarios.generator import scenario_to_dict


def negotiation_result_to_dict(result: NegotiationResult) -> dict[str, Any]:
    """Convert a negotiation result into JSON-compatible structured data."""

    return {
        "scenario": scenario_to_dict(result.scenario),
        "providers": _to_jsonable(result.provider_summary),
        "turn_history": _to_jsonable(result.turn_log),
        "agreement": _to_jsonable(result.agreement),
        "metrics": _to_jsonable(calculate_metrics(result)),
        "stopped_reason": result.stopped_reason,
    }


def negotiation_result_to_json(result: NegotiationResult, indent: int | None = 2) -> str:
    """Serialize a negotiation result to JSON."""

    return json.dumps(negotiation_result_to_dict(result), indent=indent, sort_keys=True)


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value
