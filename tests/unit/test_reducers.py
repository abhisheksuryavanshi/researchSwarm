from agents.state import _dedupe_sources, _merge_token_usage


def test_dedupe_empty_inputs():
    assert _dedupe_sources([], []) == []


def test_merge_empty_usage():
    assert _merge_token_usage({}, {}) == {}


def test_dedupe_overlapping_urls():
    ex = [{"url": "u1", "title": "a", "tool_id": "t"}]
    new = [
        {"url": "u1", "title": "b", "tool_id": "t2"},
        {"url": "u2", "title": "c", "tool_id": "t3"},
    ]
    out = _dedupe_sources(ex, new)
    assert [d["url"] for d in out] == ["u1", "u2"]
