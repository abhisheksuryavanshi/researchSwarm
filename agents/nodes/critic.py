from __future__ import annotations

import json
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.prompts import critic as prompts
from agents.response_models import CritiqueResponse
from agents.state import ResearchState
from agents.tracing import get_logger, get_tracer, tokens_from_raw_message


def route_after_critic(state: ResearchState) -> Literal["researcher", "synthesizer"]:
    if not state.get("critique_pass", False) and state.get("iteration_count", 0) < state.get(
        "max_iterations", 3
    ):
        return "researcher"
    return "synthesizer"


async def critic_node(state: ResearchState, runtime: Runtime[GraphContext]) -> dict[str, Any]:
    ctx = runtime.context
    llm = ctx["llm"]
    acfg = ctx["agent_config"]
    log = get_logger(state["trace_id"], state["session_id"], "critic")
    callbacks = []
    if (t := get_tracer(acfg)) is not None:
        callbacks.append(t)
    cb_cfg: dict[str, Any] = {"callbacks": callbacks} if callbacks else {}

    await log.ainfo("node_enter", node="critic")

    body = prompts.USER_PROMPT.format(
        query=state["query"],
        analysis=state.get("analysis") or "",
        raw_findings=json.dumps(state.get("raw_findings") or [], default=str),
        sources=json.dumps(state.get("sources") or [], default=str),
        constraints=json.dumps(state.get("constraints") or {}, default=str),
        iteration_count=state.get("iteration_count", 0),
        max_iterations=state.get("max_iterations", 3),
    )

    runnable = llm.with_structured_output(CritiqueResponse, include_raw=True)
    try:
        out = await runnable.ainvoke(
            [SystemMessage(content=prompts.SYSTEM_PROMPT), HumanMessage(content=body)],
            config=cb_cfg,
        )
    except Exception as exc:
        await log.aerror("critic_llm_failed", error=str(exc), exc_info=True)
        return {
            "critique": f"Critic LLM failed: {exc}",
            "critique_pass": False,
            "gaps": ["retry critic after resolving LLM failure"],
            "token_usage": {"critic": 0},
            "errors": [f"critic llm error: {exc}"],
            "messages": [HumanMessage(content=body), AIMessage(content="error")],
        }

    raw_msg = None
    parsed: CritiqueResponse | None = None
    if isinstance(out, dict):
        parsed = out.get("parsed")
        raw_msg = out.get("raw")
    else:
        parsed = out  # type: ignore[assignment]

    tokens = tokens_from_raw_message(raw_msg)
    if not parsed:
        await log.aerror("critic_parse_failed", body_preview=body[:200])
        return {
            "critique": "Critic could not parse structured response.",
            "critique_pass": False,
            "gaps": ["insufficient structured output from critic"],
            "token_usage": {"critic": tokens},
            "messages": [HumanMessage(content=body), AIMessage(content="parse error")],
            "errors": ["critic structured output parse failed"],
        }

    gaps = [g for g in parsed.gaps if isinstance(g, str) and g.strip()]
    if not parsed.critique_pass and not gaps:
        gaps = ["insufficient detail to verify claims against sources"]

    total = state.get("token_usage", {}).get("critic", 0) + tokens
    if total > getattr(acfg, "token_usage_warn_threshold", 100_000):
        await log.awarning("token_usage_high", agent="critic", tokens=total)

    await log.ainfo(
        "node_exit",
        node="critic",
        critique_pass=parsed.critique_pass,
        gaps=len(gaps),
    )
    return {
        "critique": parsed.critique,
        "critique_pass": parsed.critique_pass,
        "gaps": gaps,
        "token_usage": {"critic": tokens},
        "messages": [
            HumanMessage(content=body),
            AIMessage(content=parsed.model_dump_json()),
        ],
    }
