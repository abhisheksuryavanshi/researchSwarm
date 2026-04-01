from __future__ import annotations

import asyncio
from typing import Optional

import structlog
import structlog.contextvars
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph

from agents.config import AgentConfig
from agents.context import GraphContext
from agents.nodes.analyst import analyst_node
from agents.nodes.critic import critic_node, route_after_critic
from agents.nodes.researcher import researcher_node
from agents.nodes.synthesizer import synthesizer_node
from agents.state import ResearchState, merge_graph_continuation, merge_graph_defaults
from agents.tools.discovery import ToolDiscoveryTool
from agents.tools.registry_client import RegistryClient
from agents.tracing import (
    bind_langfuse_run_enabled,
    bind_trace_excerpt_max,
    reset_langfuse_run_enabled,
    reset_trace_excerpt_max,
)


class GraphBusyError(RuntimeError):
    """Another graph invocation is still running (single-flight guard)."""


_run_lock = asyncio.Lock()
_busy = False


def create_default_llm(config: AgentConfig) -> ChatGoogleGenerativeAI:
    kwargs: dict = {
        "model": config.llm_model,
        "temperature": config.llm_temperature,
        "timeout": config.llm_timeout_seconds,
        "max_retries": config.llm_max_retries,
    }
    if config.google_api_key:
        kwargs["google_api_key"] = config.google_api_key
    return ChatGoogleGenerativeAI(**kwargs)


def default_graph_context(config: Optional[AgentConfig] = None) -> GraphContext:
    cfg = config or AgentConfig()
    llm = create_default_llm(cfg)
    registry = RegistryClient(cfg)
    return GraphContext(
        llm=llm,
        registry=registry,
        agent_config=cfg,
        tool_discovery=ToolDiscoveryTool(
            registry=registry,
            llm=llm,
            config=cfg,
        ),
    )


def build_research_graph():
    g: StateGraph = StateGraph(ResearchState, context_schema=GraphContext)
    g.add_node("researcher", researcher_node)
    g.add_node("analyst", analyst_node)
    g.add_node("critic", critic_node)
    g.add_node("synthesizer", synthesizer_node)
    g.add_edge(START, "researcher")
    g.add_edge("researcher", "analyst")
    g.add_edge("analyst", "critic")
    g.add_conditional_edges(
        "critic",
        route_after_critic,
        {"researcher": "researcher", "synthesizer": "synthesizer"},
    )
    g.add_edge("synthesizer", END)
    return g.compile()


def build_synthesizer_only_graph():
    """Light path: reformat / meta without full researcher loop (User Story 4)."""
    g: StateGraph = StateGraph(ResearchState, context_schema=GraphContext)
    g.add_node("synthesizer", synthesizer_node)
    g.add_edge(START, "synthesizer")
    g.add_edge("synthesizer", END)
    return g.compile()


async def invoke_research_graph_continuation(
    compiled,
    input_state: dict,
    context: GraphContext,
) -> dict:
    """Run full graph with caller-supplied canonical ``session_id`` (no re-mint)."""
    global _busy
    raw = {k: v for k, v in input_state.items() if v is not None}
    merged = merge_graph_continuation(raw, context["agent_config"].max_iterations)
    async with _run_lock:
        if _busy:
            raise GraphBusyError("Research graph is already executing")
        _busy = True
    excerpt_tok = bind_trace_excerpt_max(context["agent_config"].trace_excerpt_max_chars)
    lf_tok = bind_langfuse_run_enabled(context["agent_config"].langfuse_enabled)
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        session_id=merged["session_id"],
        trace_id=merged["trace_id"],
        client_session_id=merged.get("client_session_id"),
        agent_id="graph",
    )
    log = structlog.get_logger()
    try:
        await log.ainfo(
            "graph_continuation_start",
            query_preview=str(merged.get("query", ""))[:200],
        )
        result = await asyncio.wait_for(
            compiled.ainvoke(merged, context=context),
            timeout=context["agent_config"].graph_timeout_seconds,
        )
        await log.ainfo("graph_continuation_complete")
        return result
    finally:
        structlog.contextvars.clear_contextvars()
        reset_trace_excerpt_max(excerpt_tok)
        reset_langfuse_run_enabled(lf_tok)
        async with _run_lock:
            _busy = False


async def invoke_light_synthesizer_graph(
    compiled,
    input_state: dict,
    context: GraphContext,
) -> dict:
    """Synthesizer-only subgraph; preserves ``session_id`` like continuation."""
    return await invoke_research_graph_continuation(compiled, input_state, context)


async def invoke_research_graph(
    compiled,
    input_state: dict,
    context: GraphContext,
) -> dict:
    global _busy
    raw = {k: v for k, v in input_state.items() if v is not None}
    merged = merge_graph_defaults(raw, context["agent_config"].max_iterations)
    async with _run_lock:
        if _busy:
            raise GraphBusyError("Research graph is already executing")
        _busy = True
    excerpt_tok = bind_trace_excerpt_max(context["agent_config"].trace_excerpt_max_chars)
    lf_tok = bind_langfuse_run_enabled(context["agent_config"].langfuse_enabled)
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        session_id=merged["session_id"],
        trace_id=merged["trace_id"],
        client_session_id=merged.get("client_session_id"),
        agent_id="graph",
    )
    log = structlog.get_logger()
    try:
        await log.ainfo(
            "graph_invoke_start",
            query_preview=str(merged.get("query", ""))[:200],
        )
        result = await asyncio.wait_for(
            compiled.ainvoke(merged, context=context),
            timeout=context["agent_config"].graph_timeout_seconds,
        )
        await log.ainfo("graph_invoke_complete")
        return result
    finally:
        structlog.contextvars.clear_contextvars()
        reset_trace_excerpt_max(excerpt_tok)
        reset_langfuse_run_enabled(lf_tok)
        async with _run_lock:
            _busy = False
