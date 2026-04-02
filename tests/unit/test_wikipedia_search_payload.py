"""Wikipedia tool payload: gsrsearch normalization for MediaWiki generator=search."""

from agents.tools.discovery import _simplify_for_wikipedia_search, build_tool_payload


def test_simplify_wh_question_strips_boilerplate():
    assert (
        _simplify_for_wikipedia_search("What is the capital of France?")
        == "capital of France"
    )
    assert _simplify_for_wikipedia_search("Where is Paris?") == "Paris"


def test_build_tool_payload_gsrsearch_uses_simplified_search():
    schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "default": "query"},
            "gsrsearch": {"type": "string"},
        },
        "required": ["gsrsearch"],
    }
    p = build_tool_payload(
        query="What is the capital of France?",
        constraints={},
        gaps=[],
        args_schema=schema,
    )
    assert p["gsrsearch"] == "capital of France"
    assert p["action"] == "query"
