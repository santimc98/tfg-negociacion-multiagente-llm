"""FastAPI application that runs and live-streams negotiations for the UI."""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app_config import load_env_file
from llm.factory import create_provider
from llm.openrouter_provider import API_KEY_ENV_VAR
from negotiation.engine import NegotiationEngine
from negotiation.mediator import RuleBasedMediator
from negotiation.models import TurnLog
from scenarios.generator import create_basic_scenario
from web.serialization import (
    result_summary_event,
    scenario_from_payload,
    scenario_to_payload,
    turn_to_event,
)

import os

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Negociación multiagente LLM")


class AgentConfig(BaseModel):
    provider: str = "mock"
    model: str = ""


class MediatorConfig(BaseModel):
    enabled: bool = False
    start_round: int = 3


class NegotiationRequest(BaseModel):
    scenario: dict[str, Any] | None = None
    buyer: AgentConfig = AgentConfig()
    seller: AgentConfig = AgentConfig()
    max_rounds: int = 6
    temperature: float = 0.2
    timeout_seconds: float = 60.0
    history_limit: int = 6
    ollama_base_url: str = "http://localhost:11434"
    mediator: MediatorConfig = MediatorConfig()


@app.on_event("startup")
def _startup() -> None:
    load_env_file()


@app.get("/api/defaults")
def get_defaults() -> dict[str, Any]:
    """Return a default scenario and provider options for the form."""

    return {
        "scenario": scenario_to_payload(create_basic_scenario()),
        "providers": ["mock", "ollama", "openrouter"],
        "openrouter_models": [
            "deepseek/deepseek-v4-pro",
            "moonshotai/kimi-k2.6",
            "z-ai/glm-5.2",
            "deepseek/deepseek-v4-flash",
            "google/gemini-3.1-flash-lite",
        ],
        "openrouter_key_present": bool(os.environ.get(API_KEY_ENV_VAR)),
    }


def _build_agent_provider(agent: AgentConfig, request: NegotiationRequest):
    if agent.provider == "mock":
        return create_provider("mock")
    if agent.provider == "ollama":
        return create_provider(
            "ollama",
            model_name=agent.model or "gemma4:26b",
            base_url=request.ollama_base_url,
            temperature=request.temperature,
            timeout_seconds=request.timeout_seconds,
            history_limit=request.history_limit,
        )
    if agent.provider == "openrouter":
        return create_provider(
            "openrouter",
            model_name=agent.model or "deepseek/deepseek-chat",
            temperature=request.temperature,
            timeout_seconds=request.timeout_seconds,
            history_limit=request.history_limit,
        )
    raise ValueError(f"Unknown provider: {agent.provider}")


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/negotiate")
def negotiate(request: NegotiationRequest) -> StreamingResponse:
    """Run a negotiation in a worker thread and stream each turn as SSE."""

    scenario = scenario_from_payload(request.scenario)
    buyer_provider = _build_agent_provider(request.buyer, request)
    seller_provider = _build_agent_provider(request.seller, request)
    mediator = RuleBasedMediator() if request.mediator.enabled else None
    engine = NegotiationEngine(max_rounds=max(1, request.max_rounds))

    events: "queue.Queue[tuple[str, dict[str, Any]] | None]" = queue.Queue()

    def on_turn(turn: TurnLog) -> None:
        events.put(("turn", turn_to_event(turn)))

    def worker() -> None:
        try:
            result = engine.run(
                scenario=scenario,
                buyer_provider=buyer_provider,
                seller_provider=seller_provider,
                mediator=mediator,
                mediation_start_round=request.mediator.start_round,
                on_turn=on_turn,
            )
            events.put(("done", result_summary_event(result)))
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            events.put(("error", {"message": str(exc)}))
        finally:
            events.put(None)

    def stream():
        yield _sse("scenario", scenario_to_payload(scenario))
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        while True:
            item = events.get()
            if item is None:
                break
            event_name, data = item
            yield _sse(event_name, data)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
