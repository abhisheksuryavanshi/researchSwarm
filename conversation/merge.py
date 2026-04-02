from __future__ import annotations

from typing import Any, Optional

from langchain_core.messages import AIMessage, HumanMessage


def merge_constraint_dicts(
    base: dict[str, Any],
    patch: Optional[dict[str, Any]],
    *,
    family_key: Optional[str] = None,
) -> dict[str, Any]:
    """
    Last-wins per top-level key (FR-010 baseline). Optional ``family_key`` reserved
    for per-key-family precedence extensions.
    """
    _ = family_key
    out = dict(base)
    if patch:
        out.update(patch)
    return out


def _messages_from_snapshot(snap: dict[str, Any]) -> list:
    raw = snap.get("messages_serial") or []
    out = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        t = m.get("type")
        content = m.get("content", "")
        if t == "human":
            out.append(HumanMessage(content=str(content)))
        elif t == "ai":
            out.append(AIMessage(content=str(content)))
    return out


def serialize_messages_for_snapshot(messages: list[Any]) -> list[dict[str, Any]]:
    serial: list[dict[str, Any]] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            serial.append({"type": "human", "content": m.content})
        elif isinstance(m, AIMessage):
            serial.append({"type": "ai", "content": m.content})
    return serial


def build_engine_input(
    snapshot: Optional[dict[str, Any]],
    user_message: str,
    trace_id: str,
    session_id: str,
    *,
    client_session_id: Optional[str] = None,
    constraints_patch: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Merge durable snapshot + new user text into a dict compatible with ``ResearchState``."""
    snap = snapshot or {}
    constraints = merge_constraint_dicts(dict(snap.get("constraints") or {}), constraints_patch)
    accumulated_context: list[str] = list(snap.get("accumulated_context") or [])
    if snap.get("synthesis"):
        accumulated_context = accumulated_context + [str(snap["synthesis"])]

    msg_list = _messages_from_snapshot(snap)
    msg_list.append(HumanMessage(content=user_message))

    return {
        "query": user_message,
        "trace_id": trace_id,
        "session_id": session_id,
        "client_session_id": client_session_id,
        "constraints": constraints,
        "accumulated_context": accumulated_context,
        "messages": msg_list,
        "raw_findings": list(snap.get("raw_findings") or []),
        "sources": list(snap.get("sources") or []),
        "analysis": str(snap.get("analysis") or ""),
        "critique": str(snap.get("critique") or ""),
        "critique_pass": bool(snap.get("critique_pass", False)),
        "gaps": list(snap.get("gaps") or []),
        "synthesis": str(snap.get("synthesis") or ""),
        "iteration_count": int(snap.get("iteration_count") or 0),
    }


def state_blob_from_graph_result(result: dict[str, Any]) -> dict[str, Any]:
    """Persistable subset of graph output for the next turn."""
    messages = result.get("messages") or []
    return {
        "query": result.get("query", ""),
        "constraints": dict(result.get("constraints") or {}),
        "accumulated_context": list(result.get("accumulated_context") or []),
        "messages_serial": serialize_messages_for_snapshot(messages),
        "raw_findings": list(result.get("raw_findings") or []),
        "sources": list(result.get("sources") or []),
        "analysis": result.get("analysis", ""),
        "critique": result.get("critique", ""),
        "critique_pass": result.get("critique_pass", False),
        "gaps": list(result.get("gaps") or []),
        "synthesis": result.get("synthesis", ""),
        "iteration_count": result.get("iteration_count", 0),
    }
