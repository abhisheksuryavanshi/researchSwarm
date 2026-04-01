from __future__ import annotations

from typing import Optional, Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from conversation.models import IntentResult


class _LLMIntentSchema(BaseModel):
    intent: str = Field(
        description="One of: new_query, refinement, reformat, meta_question",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: Optional[str] = None


class IntentClassifierProtocol(Protocol):
    async def classify(
        self, user_message: str, *, has_prior_synthesis: bool
    ) -> IntentResult: ...


class IntentClassifier:
    """Structured LLM classification (FR-004 / FR-015)."""

    def __init__(
        self,
        llm: Optional[BaseChatModel],
        *,
        confidence_threshold: float = 0.55,
    ) -> None:
        self._llm = llm
        self.confidence_threshold = confidence_threshold

    async def classify(
        self, user_message: str, *, has_prior_synthesis: bool
    ) -> IntentResult:
        if self._llm is None:
            return IntentResult(intent="new_query", confidence=1.0, rationale="no_llm_default")

        hint = (
            "The user already has a prior research synthesis in this session."
            if has_prior_synthesis
            else "This may be the first substantive turn in the session."
        )
        sys = (
            "Classify the latest user message for a research assistant. "
            "Return JSON fields intent (new_query|refinement|reformat|meta_question), "
            "confidence 0-1, optional rationale. "
            f"Context: {hint}"
        )
        runnable = self._llm.with_structured_output(_LLMIntentSchema)
        parsed = await runnable.ainvoke(
            [SystemMessage(content=sys), HumanMessage(content=user_message)]
        )
        assert isinstance(parsed, _LLMIntentSchema)
        intent_raw = parsed.intent.strip().lower().replace("-", "_")
        mapping = {
            "new_query": "new_query",
            "refinement": "refinement",
            "reformat": "reformat",
            "meta_question": "meta_question",
            "meta": "meta_question",
        }
        intent = mapping.get(intent_raw, "new_query")
        conf = float(parsed.confidence)
        if conf < self.confidence_threshold:
            return IntentResult.model_validate(
                {
                    "intent": "needs_clarification",
                    "confidence": conf,
                    "rationale": parsed.rationale,
                }
            )
        return IntentResult.model_validate(
            {
                "intent": intent,
                "confidence": conf,
                "rationale": parsed.rationale,
            }
        )
