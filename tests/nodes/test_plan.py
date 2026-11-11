
from research_agent import nodes

from research_agent.state import ResearchPlan, SearchResult, SourceSelection

class StubLLM:
    """Stands in for ChatAnthropic: records prompts, returns canned results."""

    def __init__(self, result):
        self.result = result
        self.prompts = []

    def with_structured_output(self, schema):
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.result


PLAN = ResearchPlan(
    objective="Explain X",
    search_queries=["x basics", "x criticism"],
    outline=["Background", "Findings"],
).model_dump()

def test_select_sources_drops_hallucinated_urls(monkeypatch):
    candidates = [SearchResult(title="A", url="https://a.com"), SearchResult(title="B", url="https://b.com")]
    selection = SourceSelection(urls=["https://a.com", "https://fake.invalid"], reasoning="test")
    monkeypatch.setattr(nodes.llm, "get_llm", lambda **kw: StubLLM(selection))
    out = nodes.select_sources({"plan": PLAN, "search_results": candidates})
    assert [r.url for r in out["search_results"]] == ["https://a.com"]

def test_plan_node_returns_plan_and_clears_feedback(monkeypatch):
    stub = StubLLM(ResearchPlan.model_validate(PLAN))
    monkeypatch.setattr(nodes.llm, "get_llm", lambda **kw: stub)
    out = nodes.plan({"topic": "X", "feedback": "too narrow"})
    assert out["plan"] == PLAN
    assert out["feedback"] == ""
    # human feedback must actually reach the prompt on a revision pass
    assert "too narrow" in stub.prompts[0]
