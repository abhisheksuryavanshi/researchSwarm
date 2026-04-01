from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoutePlan:
    mode: str
    engine_entry: str
    state_patch: dict | None = None


def plan_route(
    intent: str,
    confidence: float,
    *,
    session_has_snapshot: bool,
    confidence_threshold: float,
) -> RoutePlan:
    if confidence < confidence_threshold or intent == "needs_clarification":
        return RoutePlan(mode="clarify_only", engine_entry="none")
    if intent == "reformat" and session_has_snapshot:
        return RoutePlan(mode="light_reformat", engine_entry="synthesizer_only")
    if intent == "meta_question" and session_has_snapshot:
        return RoutePlan(mode="light_meta", engine_entry="synthesizer_only")
    if intent == "refinement" and session_has_snapshot:
        return RoutePlan(mode="full_graph", engine_entry="research_graph")
    if intent == "new_query":
        return RoutePlan(mode="full_graph", engine_entry="research_graph")
    if session_has_snapshot:
        return RoutePlan(mode="full_graph", engine_entry="research_graph")
    return RoutePlan(mode="full_graph", engine_entry="research_graph")
