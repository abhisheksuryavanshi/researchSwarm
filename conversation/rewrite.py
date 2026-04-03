"""Query rewriting for coreference resolution in multi-turn conversations.

When a follow-up message like "what are some of his top songs" arrives,
this module rewrites it into a self-contained query using the prior
conversation context so downstream tools receive unambiguous input.
"""

from __future__ import annotations

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

_REWRITE_SYSTEM = (
    "You are a query rewriter. The user is having a multi-turn conversation with a "
    "research assistant. Rewrite the latest user message so it is **fully self-contained** "
    "— resolve all pronouns (he, she, it, they, his, her, their, etc.) and implicit "
    "references using the conversation context below.\n\n"
    "Rules:\n"
    "- If the message is already self-contained, return it unchanged with changed=false.\n"
    "- Keep the rewritten message concise and natural.\n"
    "- Do NOT answer the question — only rewrite it.\n"
    "- Preserve the user's original intent exactly."
)


class _RewriteSchema(BaseModel):
    rewritten: str = Field(description="The rewritten, self-contained query")
    changed: bool = Field(description="True if coreferences were resolved")


async def rewrite_with_context(
    llm: BaseChatModel,
    user_message: str,
    prior_summary: str,
    *,
    max_context_chars: int = 1500,
) -> tuple[str, bool]:
    """Resolve coreferences in *user_message* using *prior_summary*.

    Returns ``(rewritten_message, was_changed)``.  Falls back to the original
    message on any LLM failure so the pipeline is never blocked by rewriting.
    """
    log = structlog.get_logger()
    if not prior_summary or not prior_summary.strip():
        return user_message, False

    context = prior_summary[:max_context_chars]
    prompt = (
        f"Conversation context (previous assistant answer):\n{context}\n\n"
        f"Latest user message:\n{user_message}"
    )
    try:
        runnable = llm.with_structured_output(_RewriteSchema)
        result = await runnable.ainvoke(
            [SystemMessage(content=_REWRITE_SYSTEM), HumanMessage(content=prompt)]
        )
        assert isinstance(result, _RewriteSchema)
        rewritten = result.rewritten.strip()
        if not rewritten:
            return user_message, False
        return rewritten, result.changed
    except Exception as exc:
        await log.awarning("query_rewrite_failed", error=str(exc))
        return user_message, False
