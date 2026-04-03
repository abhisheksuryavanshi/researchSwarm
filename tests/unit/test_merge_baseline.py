import uuid

from langchain_core.messages import HumanMessage

from conversation.merge import (
    build_engine_input,
    merge_constraint_dicts,
    state_blob_from_graph_result,
)


def test_build_engine_input_appends_user_message():
    sid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    inp = build_engine_input(None, "Second turn", tid, sid)
    assert inp["query"] == "Second turn"
    assert inp["session_id"] == sid
    assert inp["trace_id"] == tid
    assert isinstance(inp["messages"][-1], HumanMessage)


def test_build_engine_input_merges_snapshot_constraints():
    sid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    snap = {"constraints": {"scope": "eu"}, "synthesis": "Earlier answer"}
    inp = build_engine_input(snap, "Go on", tid, sid)
    assert inp["constraints"]["scope"] == "eu"
    assert any("Earlier answer" in x for x in inp["accumulated_context"])


def test_build_engine_input_new_query_resets_research_iteration_and_artifacts():
    sid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    snap = {
        "iteration_count": 9,
        "raw_findings": [{"tool_id": "x", "data": {}}],
        "sources": [{"url": "u", "title": "t", "tool_id": "x"}],
        "analysis": "old",
        "critique": "oldcrit",
        "critique_pass": True,
        "gaps": ["stale gap"],
        "synthesis": "Prior answer",
    }
    inp = build_engine_input(snap, "New topic", tid, sid, conversation_intent="new_query")
    assert inp["iteration_count"] == 0
    assert inp["raw_findings"] == []
    assert inp["sources"] == []
    assert inp["analysis"] == ""
    assert inp["critique"] == ""
    assert inp["critique_pass"] is False
    assert inp["gaps"] == []


def test_build_engine_input_refinement_keeps_snapshot_research_fields():
    sid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    snap = {
        "iteration_count": 5,
        "raw_findings": [{"tool_id": "w", "data": {"a": 1}}],
        "sources": [{"url": "https://e", "title": "E", "tool_id": "w"}],
        "analysis": "kept",
        "gaps": ["need more"],
    }
    inp = build_engine_input(snap, "Dig deeper", tid, sid, conversation_intent="refinement")
    assert inp["iteration_count"] == 0
    assert len(inp["raw_findings"]) == 1
    assert inp["analysis"] == "kept"
    assert inp["gaps"] == ["need more"]


def test_merge_constraint_dicts_last_wins():
    base = {"a": 1, "b": 2}
    assert merge_constraint_dicts(base, {"b": 3})["b"] == 3
    assert merge_constraint_dicts(base, {"b": 3})["a"] == 1


def test_state_blob_from_graph_roundtrip_fields():
    result = {
        "query": "q",
        "constraints": {"c": 1},
        "accumulated_context": ["x"],
        "messages": [HumanMessage(content="hi")],
        "synthesis": "syn",
        "raw_findings": [],
        "sources": [],
        "analysis": "",
        "critique": "",
        "critique_pass": False,
        "gaps": [],
        "iteration_count": 0,
    }
    blob = state_blob_from_graph_result(result)
    assert blob["synthesis"] == "syn"
    assert blob["messages_serial"]
