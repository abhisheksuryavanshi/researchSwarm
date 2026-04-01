from conversation.merge import build_engine_input, merge_constraint_dicts


def test_merge_constraint_nested_last_wins():
    a = {"window": "2010-2020"}
    b = {"window": "2020-2024"}
    assert merge_constraint_dicts(a, b)["window"] == "2020-2024"


def test_build_engine_input_applies_constraints_patch():
    snap = {"constraints": {"tone": "formal"}}
    inp = build_engine_input(
        snap,
        "msg",
        "00000000-0000-4000-8000-000000000001",
        "00000000-0000-4000-8000-000000000002",
        constraints_patch={"length": "short"},
    )
    assert inp["constraints"]["tone"] == "formal"
    assert inp["constraints"]["length"] == "short"
