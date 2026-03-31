from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.prompts import researcher as prompts
from agents.response_models import ToolSelectionResponse
from agents.state import ResearchState
from agents.tracing import get_logger, get_tracer, tokens_from_raw_message


def _search_summary(results: list[dict[str, Any]]) -> str:
    lines = []
    for r in results:
        caps = ", ".join(r.get("capabilities") or [])
        lines.append(
            f"- tool_id={r.get('tool_id')} name={r.get('name')} "
            f"capabilities=[{caps}] desc={r.get('description', '')[:200]}"
        )
    return "\n".join(lines) if lines else "(no tools)"


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
    capability = constraints.get("capability") if isinstance(constraints, dict) else None

    try:
        search_payload = await registry.search(capability)
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
    gaps = state.get("gaps") or []
    it = state.get("iteration_count", 0)

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

    runnable = llm.with_structured_output(ToolSelectionResponse, include_raw=True)
    try:
        out = await runnable.ainvoke(
            [
                SystemMessage(content=prompts.SYSTEM_PROMPT),
                HumanMessage(content=user_content),
            ],
            config=cb_cfg,
        )
    except Exception as exc:
        await log.aerror("researcher_llm_failed", error=str(exc), exc_info=True)
        return {
            "errors": [f"researcher llm error: {exc}"],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "token_usage": {"researcher": 0},
        }

    raw_msg = None
    selection: ToolSelectionResponse | None = None
    if isinstance(out, dict):
        selection = out.get("parsed")
        raw_msg = out.get("raw")
    else:
        selection = out  # type: ignore[assignment]

    tokens = tokens_from_raw_message(raw_msg)

    if not selection or not selection.selected_tool_ids:
        await log.awarning("researcher_no_tool_selection")
        return {
            "messages": [
                HumanMessage(content=user_content),
                AIMessage(content="no tool selection"),
            ],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "token_usage": {"researcher": tokens},
            "errors": ["researcher could not select tools"],
        }

    candidate_ids = [r["tool_id"] for r in results]
    try_order = list(dict.fromkeys(selection.selected_tool_ids + [c for c in candidate_ids]))

    new_findings: list[dict[str, Any]] = []
    new_sources: list[dict[str, str]] = []
    errs: list[str] = []
    any_success = False

    for tool_id in try_order:
        bind_info: dict[str, Any] | None = None
        try:
            bind_info = await registry.bind(tool_id)
        except Exception as exc:
            await log.aerror(
                "tool_bind_failed",
                tool_id=tool_id,
                error=str(exc),
                exc_info=True,
            )
            errs.append(f"bind failed for {tool_id}: {exc}")
            continue

        start = time.perf_counter()
        success = False
        err_msg = None
        try:
            data = await registry.invoke(
                bind_info["endpoint"],
                bind_info.get("method", "POST"),
                {},
            )
            success = True
            any_success = True
            ts = datetime.now(timezone.utc).isoformat()
            new_findings.append({"tool_id": tool_id, "data": data, "timestamp": ts})
            url = str(data.get("url") or data.get("link") or f"https://tool/{tool_id}")
            title = str(data.get("title") or bind_info.get("name") or tool_id)
            new_sources.append({"url": url, "title": title, "tool_id": tool_id})
        except Exception as exc:
            err_msg = str(exc)
            await log.aerror(
                "tool_invoke_failed",
                tool_id=tool_id,
                endpoint=bind_info.get("endpoint"),
                error=err_msg,
                exc_info=True,
            )
            errs.append(f"invoke failed for {tool_id}: {exc}")
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            await registry.log_usage(
                tool_id=tool_id,
                agent_id="researcher",
                session_id=state["session_id"],
                latency_ms=latency_ms,
                success=success,
                error_message=err_msg,
            )

        if success:
            break

    total_usage = state.get("token_usage", {}).get("researcher", 0) + tokens
    warn_thr = getattr(acfg, "token_usage_warn_threshold", 100_000)
    if total_usage > warn_thr:
        await log.awarning("token_usage_high", agent="researcher", tokens=total_usage)

    await log.ainfo("node_exit", node="researcher", findings=len(new_findings))

    if not any_success and candidate_ids:
        errs.append("all attempted tool invocations failed")

    return {
        "raw_findings": new_findings,
        "sources": new_sources,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "token_usage": {"researcher": tokens},
        "messages": [
            HumanMessage(content=user_content),
            AIMessage(content=selection.model_dump_json()),
        ],
        "errors": errs,
    }
