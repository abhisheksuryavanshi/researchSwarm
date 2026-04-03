"""Wikipedia tool payload: gsrsearch normalization for MediaWiki generator=search."""

from agents.tools.discovery import (
    _html_to_plaintext,
    _simplify_for_wikipedia_search,
    _wikipedia_title_from_query_response,
    build_tool_payload,
)


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


def test_html_to_plaintext_strips_tags_and_script():
    html = (
        '<script>alert(1)</script><style>.x{}</style>'
        '<p>Hello <b>world</b> &amp; friends.</p>'
    )
    assert _html_to_plaintext(html) == "Hello world & friends."


def test_wikipedia_title_from_query_response():
    assert (
        _wikipedia_title_from_query_response(
            {"query": {"pages": {"1": {"title": "Paris", "extract": "x"}}}}
        )
        == "Paris"
    )
    assert _wikipedia_title_from_query_response({"query": {}}) is None
    assert (
        _wikipedia_title_from_query_response(
            {"query": {"pages": {"2": {"title": "X", "missing": True}}}}
        )
        is None
    )


def test_wikipedia_title_prefers_main_article_over_season_spinoff():
    """gsrlimit=1 often returns a season page first; we rank so the series article wins."""
    data = {
        "query": {
            "pages": {
                "10": {"title": "Rick and Morty season 6", "extract": "S6…"},
                "20": {"title": "Rick and Morty", "extract": "Main…"},
                "30": {"title": "List of Rick and Morty episodes", "extract": "List…"},
            }
        }
    }
    assert _wikipedia_title_from_query_response(data) == "Rick and Morty"
