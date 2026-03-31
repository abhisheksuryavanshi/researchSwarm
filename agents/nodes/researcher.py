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


def _fallback_for_type(type_name: str | None, query: str, constraints: dict[str, Any]) -> Any:
    if type_name == "string":
        return query
    if type_name == "integer":
        return 0
    if type_name == "number":
        return 0.0
    if type_name == "boolean":
        return False
    if type_name == "array":
        return []
    if type_name == "object":
        return constraints
    return query


def _build_tool_payload(
    *,
    query: str,
    constraints: dict[str, Any],
    gaps: list[str],
    args_schema: dict[str, Any] | None,
) -> dict[str, Any]:
    schema = args_schema if isinstance(args_schema, dict) else {}
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else None
    required = schema.get("required") if isinstance(schema.get("required"), list) else []

    # If the tool has no schema hints, provide a practical default contract.
    if not properties:
        payload: dict[str, Any] = {"query": query}
        if constraints:
            payload["constraints"] = constraints
        if gaps:
            payload["gaps"] = gaps
        return payload

    payload: dict[str, Any] = {}
    lowered_constraints = {str(k).lower(): v for k, v in constraints.items()}

    for key, prop in properties.items():
        key_l = key.lower()
        prop_d = prop if isinstance(prop, dict) else {}

        if key_l in {"query", "q", "question", "prompt", "search_query", "search_term", "text"}:
            payload[key] = query
            continue
        if key_l in {"constraints", "filters"}:
            payload[key] = constraints
            continue
        if key_l in {"gaps", "missing_topics", "follow_up_topics"}:
            payload[key] = gaps
            continue
        if key_l in lowered_constraints:
            payload[key] = lowered_constraints[key_l]
            continue
        if key in constraints:
            payload[key] = constraints[key]
            continue
        if "default" in prop_d:
            payload[key] = prop_d["default"]

    # Fill required keys if still missing with type-aware fallbacks.
    for req in required:
        if req not in payload:
            rprop = properties.get(req, {})
            rtype = rprop.get("type") if isinstance(rprop, dict) else None
            payload[req] = _fallback_for_type(rtype, query, constraints)

    return payload


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

    # Spec: invoke only the tools explicitly selected by the LLM (no non-selected registry candidates).
    # Keep order stable while deduplicating.
    selected_ids = list(dict.fromkeys(selection.selected_tool_ids))

    new_findings: list[dict[str, Any]] = []
    new_sources: list[dict[str, str]] = []
    errs: list[str] = []
    any_success = False

    for tool_id in selected_ids:
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
            payload = _build_tool_payload(
                query=state["query"],
                constraints=constraints if isinstance(constraints, dict) else {},
                gaps=gaps if isinstance(gaps, list) else [],
                args_schema=bind_info.get("args_schema"),
            )
            data = await registry.invoke(
                bind_info["endpoint"],
                bind_info.get("method", "POST"),
                payload,
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

        # Do not break on first success: if the LLM selected multiple tools (top-k), we should
        # gather findings from all of them.

    total_usage = state.get("token_usage", {}).get("researcher", 0) + tokens
    warn_thr = getattr(acfg, "token_usage_warn_threshold", 100_000)
    if total_usage > warn_thr:
        await log.awarning("token_usage_high", agent="researcher", tokens=total_usage)

    await log.ainfo("node_exit", node="researcher", findings=len(new_findings))

    if not any_success and selected_ids:
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
