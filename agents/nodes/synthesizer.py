from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from agents.context import GraphContext
from agents.prompts import synthesizer as prompts
from agents.response_models import SynthesisResponse
from agents.state import ResearchState
from agents.tracing import get_logger, get_tracer, llm_invoke_config, tokens_from_raw_message


async def synthesizer_node(state: ResearchState, runtime: Runtime[GraphContext]) -> dict[str, Any]:
    ctx = runtime.context
    llm = ctx["llm"]
    acfg = ctx["agent_config"]
    log = get_logger(
        state["trace_id"],
        state["session_id"],
        "synthesizer",
        state.get("client_session_id"),
    )
    callbacks = []
    if (t := get_tracer(acfg, trace_id=state["trace_id"])) is not None:
        callbacks.append(t)
    cb_cfg = llm_invoke_config(state, callbacks)

    await log.ainfo("node_enter", node="synthesizer")

    cp = state.get("critique_pass", False)
    body = prompts.USER_PROMPT.format(
        query=state["query"],
        analysis=state.get("analysis") or "",
        raw_findings=json.dumps(state.get("raw_findings") or [], default=str),
        sources=json.dumps(state.get("sources") or [], default=str),
        critique=state.get("critique") or "",
        critique_pass=cp,
        constraints=json.dumps(state.get("constraints") or {}, default=str),
        accumulated_context=json.dumps(state.get("accumulated_context") or [], default=str),
    )

    runnable = llm.with_structured_output(SynthesisResponse, include_raw=True)
    try:
        out = await runnable.ainvoke(
            [SystemMessage(content=prompts.SYSTEM_PROMPT), HumanMessage(content=body)],
            config=cb_cfg if cb_cfg else None,
        )
    except Exception as exc:
        await log.aerror("synthesizer_llm_failed", error=str(exc), exc_info=True)
        srcs = state.get("sources") or []
        cite = srcs[0].get("url", "source") if srcs else "n/a"
        fallback = f"## Error\nSynthesis failed: {exc}\n\nSee `{cite}`."
        return {
            "synthesis": fallback,
            "token_usage": {"synthesizer": 0},
            "errors": [f"synthesizer llm error: {exc}"],
            "messages": [HumanMessage(content=body), AIMessage(content="error")],
        }

    raw_msg = None
    parsed: SynthesisResponse | None = None
    if isinstance(out, dict):
        parsed = out.get("parsed")
        raw_msg = out.get("raw")
    else:
        parsed = out  # type: ignore[assignment]

    tokens = tokens_from_raw_message(raw_msg)
    text = parsed.synthesis if parsed else ""

    if not cp and "limitation" not in text.lower():
        text = f"{text}\n\n## Limitations\nQuality gate did not pass; verify claims carefully."

    total = state.get("token_usage", {}).get("synthesizer", 0) + tokens
    if total > getattr(acfg, "token_usage_warn_threshold", 100_000):
        await log.awarning("token_usage_high", agent="synthesizer", tokens=total)

    await log.ainfo("node_exit", node="synthesizer")
    return {
        "synthesis": text,
        "token_usage": {"synthesizer": tokens},
        "messages": [HumanMessage(content=body), AIMessage(content=text)],
    }
