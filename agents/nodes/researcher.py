from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.prompts import researcher as prompts
from agents.response_models import ToolDiscoveryInput, ToolDiscoveryResult
from agents.state import ResearchState
from agents.tools.discovery import ToolDiscoveryTool, _search_summary
from agents.tracing import get_logger, get_tracer


async def researcher_node(state: ResearchState, runtime: Runtime[GraphContext]) -> dict[str, Any]:
    ctx = runtime.context
    llm = ctx["llm"]
    registry = ctx["registry"]
    acfg = ctx["agent_config"]

    log = get_logger(state["trace_id"], state["session_id"], "researcher")
    callbacks = []
    if (t := get_tracer(acfg)) is not None:
        callbacks.append(t)
    cb_cfg: dict[str, Any] = {"callbacks": callbacks} if callbacks else {}

    await log.ainfo("node_enter", node="researcher")

    constraints = state.get("constraints") or {}
    if not isinstance(constraints, dict):
        constraints = {}
    cap_raw = constraints.get("capability")
    capability = "" if cap_raw is None else str(cap_raw).strip()

    gaps = state.get("gaps") or []
    if not isinstance(gaps, list):
        gaps = []
    it = state.get("iteration_count", 0)

    try:
        search_payload = await registry.search(
            capability or None,
            constraints=constraints,
        )
    except Exception as exc:
        await log.aerror("registry_search_failed", error=str(exc), exc_info=True)
        return {
            "errors": [f"registry search failed: {exc}"],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "token_usage": {"researcher": 0},
        }

    results = search_payload.get("results") or []
    summary = _search_summary(results)
    constraints_s = json.dumps(constraints, default=str)

    if it > 0 and gaps:
        user_content = prompts.REFINEMENT_PROMPT.format(
            iteration_count=it,
            gaps="\n".join(f"- {g}" for g in gaps),
            query=state["query"],
            constraints=constraints_s,
            search_summary=summary,
        )
    else:
        user_content = prompts.USER_PROMPT.format(
            query=state["query"],
            constraints=constraints_s,
            search_summary=summary,
        )

    tool_discovery = ctx.get("tool_discovery")
    if callbacks:
        tool_discovery = ToolDiscoveryTool(
            registry=registry,
            llm=llm,
            config=acfg,
            callbacks=callbacks,
        )
    elif tool_discovery is None:
        tool_discovery = ToolDiscoveryTool(
            registry=registry,
            llm=llm,
            config=acfg,
        )

    td_input = ToolDiscoveryInput(
        capability=capability,
        query=state["query"],
        constraints=constraints,
        gaps=gaps,
        agent_id="researcher",
        session_id=state["session_id"],
        trace_id=state["trace_id"],
    )

    try:
        raw_out = await tool_discovery.ainvoke(
            td_input.model_dump(),
            config=cb_cfg or None,
        )
    except Exception as exc:
        await log.aerror("tool_discovery_failed", error=str(exc), exc_info=True)
        return {
            "errors": [f"tool discovery failed: {exc}"],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "token_usage": {"researcher": 0},
        }

    if isinstance(raw_out, str):
        parsed = ToolDiscoveryResult.model_validate_json(raw_out)
    else:
        parsed = ToolDiscoveryResult.model_validate(raw_out)

    tokens = 100
    errs: list[str] = []
    new_findings: list[dict[str, Any]] = []
    new_sources: list[dict[str, str]] = []

    if parsed.error and not parsed.success:
        errs.append(parsed.error)

    for att in parsed.attempts:
        if not att.success and att.error_message:
            errs.append(f"invoke failed for {att.tool_id}: {att.error_message}")

    practical: dict[str, Any] = {}
    if isinstance(parsed.data, dict):
        practical = parsed.data.get("raw_data")
        if not isinstance(practical, dict):
            practical = parsed.data

    if parsed.success and parsed.tool_id:
        ts = datetime.now(timezone.utc).isoformat()
        new_findings.append(
            {"tool_id": parsed.tool_id, "data": practical, "timestamp": ts}
        )
        src = parsed.source or {}
        new_sources.append(
            {
                "url": src.get("url")
                or str(practical.get("url") or practical.get("link") or ""),
                "title": src.get("title") or str(practical.get("title") or parsed.tool_id),
                "tool_id": parsed.tool_id,
            }
        )
    elif parsed.attempts and not parsed.success:
        errs.append("all attempted tool invocations failed")

    total_usage = state.get("token_usage", {}).get("researcher", 0) + tokens
    warn_thr = getattr(acfg, "token_usage_warn_threshold", 100_000)
    if total_usage > warn_thr:
        await log.awarning("token_usage_high", agent="researcher", tokens=total_usage)

    await log.ainfo("node_exit", node="researcher", findings=len(new_findings))

    return {
        "raw_findings": new_findings,
        "sources": new_sources,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "token_usage": {"researcher": tokens},
        "messages": [
            HumanMessage(content=user_content),
            AIMessage(content=raw_out if isinstance(raw_out, str) else json.dumps(raw_out)),
        ],
        "errors": errs,
    }
