
from research_agent import nodes

from research_agent.state import ResearchPlan

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



def test_search_broadens_queries_on_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(nodes.search_tool, "web_search", lambda q, **kw: calls.append(q) or [])
    nodes.search({"topic": "X", "plan": PLAN, "search_round": 1})
    assert "X overview" in calls  # round 2 adds broadened queries
    assert "x basics" in calls

