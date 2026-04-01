import uuid

import pytest

from agents.state import merge_graph_continuation, validate_continuation_input


def test_validate_continuation_rejects_non_uuid_session():
    with pytest.raises(ValueError, match="UUID"):
        validate_continuation_input(
            {
                "query": "q",
                "trace_id": str(uuid.uuid4()),
                "session_id": "not-a-uuid",
            }
        )


def test_merge_graph_continuation_preserves_session_id():
    sid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    out = merge_graph_continuation(
        {"query": "x", "trace_id": tid, "session_id": sid},
        default_max_iterations=3,
    )
    assert out["session_id"] == sid
