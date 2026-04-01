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
