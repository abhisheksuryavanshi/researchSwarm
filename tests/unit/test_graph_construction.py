from agents.graph import build_research_graph


def test_build_research_graph_structure():
    g = build_research_graph()
    graph = g.get_graph()
    names = {n for n in graph.nodes if not n.startswith("__")}
    assert names == {"researcher", "analyst", "critic", "synthesizer"}
