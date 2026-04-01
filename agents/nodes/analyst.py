from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.prompts import analyst as prompts
from agents.response_models import AnalysisResponse
from agents.state import ResearchState
from agents.tracing import get_logger, get_tracer, llm_invoke_config, tokens_from_raw_message


async def analyst_node(state: ResearchState, runtime: Runtime[GraphContext]) -> dict[str, Any]:
    ctx = runtime.context
    llm = ctx["llm"]
    acfg = ctx["agent_config"]
    log = get_logger(
        state["trace_id"],
        state["session_id"],
        "analyst",
        state.get("client_session_id"),
    )
    callbacks = []
    if (t := get_tracer(acfg, trace_id=state["trace_id"])) is not None:
        callbacks.append(t)
    cb_cfg = llm_invoke_config(state, callbacks)

    await log.ainfo("node_enter", node="analyst")

    findings = state.get("raw_findings") or []
    sources = state.get("sources") or []
    constraints = state.get("constraints") or {}
    acc = state.get("accumulated_context") or []

    body = prompts.USER_PROMPT.format(
        query=state["query"],
        raw_findings=json.dumps(findings, default=str),
        sources=json.dumps(sources, default=str),
        constraints=json.dumps(constraints, default=str),
        accumulated_context=json.dumps(acc, default=str),
    )

    runnable = llm.with_structured_output(AnalysisResponse, include_raw=True)
    try:
        out = await runnable.ainvoke(
            [SystemMessage(content=prompts.SYSTEM_PROMPT), HumanMessage(content=body)],
            config=cb_cfg if cb_cfg else None,
        )
    except Exception as exc:
        await log.aerror("analyst_llm_failed", error=str(exc), exc_info=True)
        return {
            "analysis": f"*LLM error; no analysis produced.* ({exc})",
            "token_usage": {"analyst": 0},
            "errors": [f"analyst llm error: {exc}"],
            "messages": [HumanMessage(content=body), AIMessage(content="error")],
        }

    raw_msg = None
    parsed: Optional[AnalysisResponse] = None
    if isinstance(out, dict):
        parsed = out.get("parsed")
        raw_msg = out.get("raw")
    else:
        parsed = out  # type: ignore[assignment]

    tokens = tokens_from_raw_message(raw_msg)
    text = parsed.analysis if parsed else ""

    if not findings and "lack" not in text.lower() and "no data" not in text.lower():
        text = (
            f"{text}\n\n*Note: no raw findings were available — conclusions are limited.*"
        )

    total = state.get("token_usage", {}).get("analyst", 0) + tokens
    if total > getattr(acfg, "token_usage_warn_threshold", 100_000):
        await log.awarning("token_usage_high", agent="analyst", tokens=total)

    await log.ainfo("node_exit", node="analyst")
    return {
        "analysis": text,
        "token_usage": {"analyst": tokens},
        "messages": [HumanMessage(content=body), AIMessage(content=text)],
    }
