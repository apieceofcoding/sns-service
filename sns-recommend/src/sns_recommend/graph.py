from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .config import settings
from .db import connection
from .event_queue import (
    allocate_generation,
    claim,
    enqueue,
    finish,
    heartbeat,
    renew,
)
from .feed import publish
from .ranking import (
    diversify,
    prepare_inputs,
    ranking_strategy,
    rerank_candidates,
    validate_ranking,
)

GRAPH_VERSION = "sns-feed-behavior-v3"


class FeedState(TypedDict, total=False):
    user_id: int
    event_id: str
    claim_id: str
    generation: int
    snapshot_id: str
    created_at: float
    graph_version: str
    inputs: dict[str, Any]
    response: dict[str, Any]
    ordered: list[int]
    valid: bool
    strategy: str
    error: str
    published: bool


def guard(state: FeedState) -> None:
    """Stop this node if another worker took over the request."""
    renew({"id": state["event_id"], "claim_id": state["claim_id"]})


def make_graph(
    checkpointer: BaseCheckpointSaver[Any], pause: bool = False
) -> CompiledStateGraph[FeedState, None, FeedState, FeedState]:
    def retrieve(state: FeedState) -> FeedState:
        guard(state)
        return {"inputs": prepare_inputs(state["user_id"])}

    def rerank(state: FeedState) -> FeedState:
        guard(state)
        try:
            result = rerank_candidates(state["inputs"])
            strategy = ranking_strategy(result["mode"])
            answer: FeedState = {"response": result, "strategy": strategy, "error": ""}
        except Exception as exc:
            answer = {
                "response": {"ordered_ids": [], "mode": settings().model_mode, "usage": {}},
                "error": type(exc).__name__,
            }
        return answer

    def validate(state: FeedState) -> FeedState:
        guard(state)
        try:
            ids = validate_ranking(
                state["inputs"]["candidates"], state["response"].get("ordered_ids")
            )
            return {"ordered": ids, "valid": not bool(state.get("error"))}
        except ValueError:
            return {"valid": False, "error": "InvalidRanking"}

    def fallback(state: FeedState) -> FeedState:
        guard(state)
        return {
            "ordered": [p["id"] for p in state["inputs"]["candidates"]],
            "strategy": "rules_fallback",
        }

    def diversity(state: FeedState) -> FeedState:
        guard(state)
        return {"ordered": diversify(state["inputs"]["candidates"], state["ordered"])}

    def publish_feed(state: FeedState) -> FeedState:
        guard(state)
        with connection() as original:
            event = original.execute(
                "SELECT * FROM user_events WHERE id=%s FOR UPDATE", (state["event_id"],)
            ).fetchone()
            if (
                event is None
                or str(event["claim_id"]) != state["claim_id"]
                or event["processed_at"] is not None
                or event["locked_until"] <= datetime.now(UTC)
            ):
                return {"published": False}
            if datetime.now(UTC).timestamp() - state["created_at"] > settings().snapshot_ttl:
                return {"published": False}
            published = publish(
                state["user_id"],
                state["ordered"],
                state["strategy"],
                state["generation"],
                state["snapshot_id"],
                state["created_at"],
            )
        return {"published": published}

    builder = StateGraph(FeedState)
    for name, node in [
        ("retrieve", retrieve),
        ("rerank", rerank),
        ("validate", validate),
        ("fallback", fallback),
        ("diversify", diversity),
        ("publish", publish_feed),
    ]:
        builder.add_node(name, node)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "rerank")
    builder.add_edge("rerank", "validate")
    builder.add_conditional_edges("validate", lambda s: "diversify" if s["valid"] else "fallback")
    builder.add_edge("fallback", "diversify")
    builder.add_edge("diversify", "publish")
    builder.add_edge("publish", END)
    return builder.compile(checkpointer=checkpointer, interrupt_after=["rerank"] if pause else [])


def run_graph(event: dict[str, Any], pause: bool = False) -> dict[str, Any]:
    with PostgresSaver.from_conn_string(settings().database_url) as saver:
        saver.setup()
        graph = make_graph(saver, pause)
        config: RunnableConfig = {"configurable": {"thread_id": "behavior:" + str(event["id"])}}
        saved = graph.get_state(config)
        if saved.values:
            if saved.values["graph_version"] != GRAPH_VERSION:
                raise ValueError("unsupported graph version")
            graph.update_state(config, {"claim_id": str(event["claim_id"])}, as_node=None)
            result = graph.invoke(None, config)
        else:
            result = graph.invoke(
                {
                    "user_id": event["user_id"],
                    "event_id": str(event["id"]),
                    "claim_id": str(event["claim_id"]),
                    "generation": allocate_generation(),
                    "snapshot_id": str(event["id"]),
                    # The list's age starts now, not when the request was queued.
                    "created_at": datetime.now(UTC).timestamp(),
                    "graph_version": GRAPH_VERSION,
                },
                config,
            )
        if graph.get_state(config).next:
            with connection() as conn:
                conn.execute(
                    "UPDATE user_events SET locked_until=now() WHERE id=%s AND claim_id=%s",
                    (event["id"], event["claim_id"]),
                )
            return {"paused": True, "event_id": str(event["id"]), "next": "validate"}
    if not finish(event):
        raise RuntimeError("event lease lost")
    return {
        "event_id": str(event["id"]),
        "strategy": result["strategy"],
        "post_ids": result["ordered"],
        "published": result.get("published", False),
    }


def start_graph(user_id: int, pause: bool = False) -> dict[str, Any]:
    event = claim(event_id=enqueue(user_id))
    if event is None:
        raise RuntimeError("event already owned by a worker")
    if pause:
        return run_graph(event, pause)
    with heartbeat(event):
        result = run_graph(event)
    return result
