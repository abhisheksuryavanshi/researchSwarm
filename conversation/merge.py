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
    conversation_intent: str = "new_query",
    rewritten_query: Optional[str] = None,
) -> dict[str, Any]:
    """Merge durable snapshot + new user text into a dict compatible with ``ResearchState``.

    Each HTTP turn runs one graph invocation; ``iteration_count`` always starts at 0 so the
    researcher↔critic loop has a full ``max_iterations`` budget. For ``new_query``, prior
    research artifacts from the snapshot are cleared so the researcher is not steered by stale
    gaps or findings from an unrelated question.

    When *rewritten_query* is provided (coreference-resolved version of *user_message*),
    it is used as the ``query`` field so the researcher and downstream nodes receive an
    unambiguous query.  The original *user_message* is still appended to the ``messages``
    list so the conversation transcript remains faithful to what the user actually typed.
    """
    snap = snapshot or {}
    constraints = merge_constraint_dicts(dict(snap.get("constraints") or {}), constraints_patch)
    accumulated_context: list[str] = list(snap.get("accumulated_context") or [])
    if snap.get("synthesis"):
        accumulated_context = accumulated_context + [str(snap["synthesis"])]

    msg_list = _messages_from_snapshot(snap)
    msg_list.append(HumanMessage(content=user_message))

    intent = (conversation_intent or "new_query").strip().lower()
    if intent == "new_query":
        raw_findings: list = []
        sources: list = []
        analysis = ""
        critique = ""
        critique_pass = False
        gaps: list = []
    else:
        raw_findings = list(snap.get("raw_findings") or [])
        sources = list(snap.get("sources") or [])
        analysis = str(snap.get("analysis") or "")
        critique = str(snap.get("critique") or "")
        critique_pass = bool(snap.get("critique_pass", False))
        gaps = list(snap.get("gaps") or [])

    return {
        "query": rewritten_query or user_message,
        "trace_id": trace_id,
        "session_id": session_id,
        "client_session_id": client_session_id,
        "constraints": constraints,
        "accumulated_context": accumulated_context,
        "messages": msg_list,
        "raw_findings": raw_findings,
        "sources": sources,
        "analysis": analysis,
        "critique": critique,
        "critique_pass": critique_pass,
        "gaps": gaps,
        "synthesis": str(snap.get("synthesis") or ""),
        "iteration_count": 0,
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
