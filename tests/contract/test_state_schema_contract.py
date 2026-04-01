import uuid

import pytest

from agents.state import (
    ResearchState,
    _dedupe_sources,
    _merge_token_usage,
    merge_graph_defaults,
    validate_graph_input,
)


def test_validate_accepts_minimal_input():
    s = {
        "query": "q",
        "trace_id": str(uuid.uuid4()),
        "session_id": "sess",
    }
    validate_graph_input({**s, "max_iterations": 3})


def test_validate_rejects_empty_query():
    with pytest.raises(ValueError, match="query"):
        validate_graph_input(
            {
                "query": "",
                "trace_id": str(uuid.uuid4()),
                "session_id": "s",
            }
        )


def test_validate_rejects_bad_max_iterations():
    with pytest.raises(ValueError, match="max_iterations"):
        validate_graph_input(
            {
                "query": "q",
                "trace_id": str(uuid.uuid4()),
                "session_id": "s",
                "max_iterations": 6,
            }
        )


def test_validate_rejects_bad_trace_id():
    with pytest.raises(ValueError, match="trace_id"):
        validate_graph_input(
            {
                "query": "q",
                "trace_id": "not-a-uuid",
                "session_id": "s",
            }
        )


def test_dedupe_sources_by_url():
    a = [{"url": "http://a", "title": "A", "tool_id": "t1"}]
    b = [
        {"url": "http://a", "title": "dup", "tool_id": "t2"},
        {"url": "http://b", "title": "B", "tool_id": "t3"},
    ]
    merged = _dedupe_sources(a, b)
    assert len(merged) == 2
    urls = {x["url"] for x in merged}
    assert urls == {"http://a", "http://b"}


def test_merge_token_usage_sums():
    assert _merge_token_usage({"a": 1, "b": 2}, {"a": 3, "c": 4}) == {"a": 4, "b": 2, "c": 4}


def test_merge_graph_defaults_and_optional_fields():
    tid = str(uuid.uuid4())
    m = merge_graph_defaults({"query": "why", "trace_id": tid, "session_id": "s1"}, 3)
    assert m["constraints"] == {}
    assert m["iteration_count"] == 0
    assert m["max_iterations"] == 3
    assert m.get("client_session_id") == "s1"
    uuid.UUID(m["session_id"])  # canonical server session


def test_merge_prefers_explicit_client_session_id_over_legacy_session_id():
    tid = str(uuid.uuid4())
    m = merge_graph_defaults(
        {
            "query": "why",
            "trace_id": tid,
            "session_id": "legacy",
            "client_session_id": "explicit-client",
        },
        3,
    )
    assert m.get("client_session_id") == "explicit-client"
    assert m["session_id"] != "legacy"


def test_validate_rejects_non_string_client_session_id():
    tid = str(uuid.uuid4())
    with pytest.raises(ValueError, match="client_session_id"):
        validate_graph_input(
            {
                "query": "q",
                "trace_id": tid,
                "session_id": str(uuid.uuid4()),
                "client_session_id": 123,  # type: ignore[dict-item]
                "max_iterations": 3,
            }
        )


def test_research_state_is_typeddict():
    assert ResearchState.__total__ is False
