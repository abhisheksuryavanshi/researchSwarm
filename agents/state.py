from __future__ import annotations

import operator
import uuid
from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


def _dedupe_sources(
    existing: list[dict[str, str]], new: list[dict[str, str]]
) -> list[dict[str, str]]:
    seen = {s["url"] for s in existing}
    merged = list(existing)
    for s in new:
        if s["url"] not in seen:
            merged.append(s)
            seen.add(s["url"])
    return merged


def _merge_token_usage(existing: dict[str, int], new: dict[str, int]) -> dict[str, int]:
    merged = dict(existing)
    for k, v in new.items():
        merged[k] = merged.get(k, 0) + v
    return merged


class ResearchState(TypedDict, total=False):
    query: str
    constraints: dict[str, Any]
    accumulated_context: Annotated[list[str], operator.add]
    messages: Annotated[list[AnyMessage], add_messages]
    trace_id: str
    session_id: str
    client_session_id: Optional[str]
    max_iterations: int
    raw_findings: Annotated[list[dict[str, Any]], operator.add]
    sources: Annotated[list[dict[str, str]], _dedupe_sources]
    analysis: str
    critique: str
    critique_pass: bool
    gaps: list[str]
    synthesis: str
    iteration_count: int
    token_usage: Annotated[dict[str, int], _merge_token_usage]
    errors: Annotated[list[str], operator.add]


def validate_graph_input(state: dict[str, Any]) -> None:
    q = state.get("query")
    if not isinstance(q, str) or len(q.strip()) == 0:
        raise ValueError("query must be a non-empty string")

    tid = state.get("trace_id")
    if not isinstance(tid, str) or len(tid) == 0:
        raise ValueError("trace_id must be a non-empty string")
    try:
        uuid.UUID(tid)
    except ValueError as e:
        raise ValueError("trace_id must be a valid UUID string") from e

    sid = state.get("session_id")
    if not isinstance(sid, str) or len(sid.strip()) == 0:
        raise ValueError("session_id must be a server-issued non-empty string")

    csid = state.get("client_session_id")
    if csid is not None and not isinstance(csid, str):
        raise ValueError("client_session_id must be a string when provided")

    mi = state.get("max_iterations", 3)
    if not isinstance(mi, int) or not (1 <= mi <= 5):
        raise ValueError("max_iterations must be between 1 and 5 inclusive")

    if "constraints" in state and not isinstance(state["constraints"], dict):
        raise ValueError("constraints must be a dict when provided")


def validate_continuation_input(state: dict[str, Any]) -> None:
    """Stricter validation for follow-up turns: canonical ``session_id`` must be a UUID string."""
    validate_graph_input(state)
    sid = state.get("session_id")
    if not isinstance(sid, str):
        raise ValueError("session_id must be a string for continuation")
    try:
        uuid.UUID(sid.strip())
    except ValueError as e:
        raise ValueError("session_id must be a valid UUID string for continuation") from e


def merge_graph_continuation(state: dict[str, Any], default_max_iterations: int) -> dict[str, Any]:
    """Merge defaults for a continuation run without minting a new ``session_id``."""
    incoming = {k: v for k, v in state.items() if v is not None}
    out: dict[str, Any] = {
        "constraints": {},
        "accumulated_context": [],
        "messages": [],
        "max_iterations": default_max_iterations,
        "raw_findings": [],
        "sources": [],
        "analysis": "",
        "critique": "",
        "critique_pass": False,
        "gaps": [],
        "synthesis": "",
        "iteration_count": 0,
        "token_usage": {},
        "errors": [],
    }
    out.update(incoming)
    validate_continuation_input(out)
    return out


def merge_graph_defaults(state: dict[str, Any], default_max_iterations: int) -> dict[str, Any]:
    incoming = dict(state)
    explicit_client = incoming.pop("client_session_id", None)
    legacy_session = incoming.pop("session_id", None)

    client_session_id: Optional[str] = None
    if isinstance(explicit_client, str) and explicit_client.strip():
        client_session_id = explicit_client.strip()
    elif isinstance(legacy_session, str) and legacy_session.strip():
        client_session_id = legacy_session.strip()

    canonical_session_id = str(uuid.uuid4())

    out: dict[str, Any] = {
        "constraints": {},
        "accumulated_context": [],
        "messages": [],
        "max_iterations": default_max_iterations,
        "raw_findings": [],
        "sources": [],
        "analysis": "",
        "critique": "",
        "critique_pass": False,
        "gaps": [],
        "synthesis": "",
        "iteration_count": 0,
        "token_usage": {},
        "errors": [],
        "session_id": canonical_session_id,
        **incoming,
    }
    if client_session_id is not None:
        out["client_session_id"] = client_session_id
    validate_graph_input(out)
    return out
