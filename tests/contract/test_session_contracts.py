from conversation.authz import SESSION_NOT_FOUND
from conversation.models import IdempotencyMismatchBody, SessionDegradedErrorBody, TurnResult


def test_fr016_denial_body_stable():
    a = dict(SESSION_NOT_FOUND)
    b = dict(SESSION_NOT_FOUND)
    assert a == b
    assert a["error"] == "session_not_found"


def test_turn_result_contract_keys():
    tr = TurnResult(
        turn_index=1,
        assistant_message="hi",
        intent="refinement",
        intent_confidence=0.9,
        trace_id="00000000-0000-4000-8000-000000000001",
    )
    d = tr.model_dump()
    assert set(d.keys()) >= {
        "turn_index",
        "assistant_message",
        "intent",
        "intent_confidence",
        "degraded_mode",
        "trace_id",
    }


def test_degraded_error_shape():
    b = SessionDegradedErrorBody().model_dump()
    assert b["degraded_mode"] is True


def test_idempotency_mismatch_shape():
    b = IdempotencyMismatchBody().model_dump()
    assert b["error"] == "idempotency_mismatch"
