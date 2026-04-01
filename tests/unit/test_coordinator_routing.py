import pytest

from conversation.routing import plan_route


@pytest.mark.parametrize(
    ("intent", "conf", "has_snap", "mode"),
    [
        ("new_query", 0.9, False, "full_graph"),
        ("reformat", 0.9, True, "light_reformat"),
        ("meta_question", 0.9, True, "light_meta"),
        ("refinement", 0.9, True, "full_graph"),
    ],
)
def test_plan_route_modes(intent, conf, has_snap, mode):
    plan = plan_route(
        intent,
        conf,
        session_has_snapshot=has_snap,
        confidence_threshold=0.55,
    )
    assert plan.mode == mode


def test_low_confidence_clarify():
    plan = plan_route(
        "new_query",
        0.2,
        session_has_snapshot=True,
        confidence_threshold=0.55,
    )
    assert plan.mode == "clarify_only"
