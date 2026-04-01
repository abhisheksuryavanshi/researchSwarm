import pytest

from conversation.intent import IntentClassifier


@pytest.mark.asyncio
async def test_classifier_no_llm_defaults_new_query():
    c = IntentClassifier(None, confidence_threshold=0.55)
    r = await c.classify("anything", has_prior_synthesis=True)
    assert r.intent == "new_query"
    assert r.confidence == 1.0
