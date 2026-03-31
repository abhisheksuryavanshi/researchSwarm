from __future__ import annotations

import asyncio

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph

from agents.config import AgentConfig
from agents.context import GraphContext
from agents.nodes.analyst import analyst_node
from agents.nodes.critic import critic_node, route_after_critic
from agents.nodes.researcher import researcher_node
from agents.nodes.synthesizer import synthesizer_node
from agents.state import ResearchState, merge_graph_defaults
from agents.tools.registry_client import RegistryClient


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


def default_graph_context(config: AgentConfig | None = None) -> GraphContext:
    cfg = config or AgentConfig()
    return GraphContext(
        llm=create_default_llm(cfg),
        registry=RegistryClient(cfg),
        agent_config=cfg,
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
    try:
        async with asyncio.timeout(context["agent_config"].graph_timeout_seconds):
            return await compiled.ainvoke(merged, context=context)
    finally:
        async with _run_lock:
            _busy = False
