
from research_agent import nodes

from research_agent.state import ResearchPlan

from research_agent.discovery.source_selection import (
    SourceSelectionConfig,
    SourceSelectionMode,
)

from research_agent.discovery.models import SearchResult

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


def test_search_filters_verified_sources(monkeypatch):
    results = [
        SearchResult(
            title="BBC article",
            url="https://www.bbc.com/news/example",
            snippet="BBC result",
        ),
        SearchResult(
            title="Unknown article",
            url="https://unknown.com/article",
            snippet="Unknown result",
        ),
    ]

    monkeypatch.setattr(
        nodes.search_tool,
        "web_search",
        lambda q, **kw: results,
    )

    state = {
        "topic": "X",
        "plan": PLAN,
        "search_round": 0,
        "source_selection": SourceSelectionConfig(
            mode=SourceSelectionMode.VERIFIED_ONLY,
            verified_domains={"bbc.com"},
        ),
    }

    result = nodes.search(state)

    assert len(result["search_results"]) == 1
    assert result["search_results"][0].url == (
        "https://www.bbc.com/news/example"
    )


def test_search_returns_all_sources_when_mode_is_all(monkeypatch):
    results = [
        SearchResult(
            title="BBC article",
            url="https://www.bbc.com/news/example",
        ),
        SearchResult(
            title="Unknown article",
            url="https://unknown.com/article",
        ),
    ]

    monkeypatch.setattr(
        nodes.search_tool,
        "web_search",
        lambda q, **kw: results,
    )

    state = {
        "topic": "X",
        "plan": PLAN,
        "search_round": 0,
        "source_selection": SourceSelectionConfig(
            mode=SourceSelectionMode.ALL,
        ),
    }

    result = nodes.search(state)

    assert len(result["search_results"]) == 2


def test_search_preserves_original_results(monkeypatch):
    original_result = SearchResult(
        title="BBC article",
        url="https://www.bbc.com/news/example",
    )

    monkeypatch.setattr(
        nodes.search_tool,
        "web_search",
        lambda q, **kw: [original_result],
    )

    state = {
        "topic": "X",
        "plan": PLAN,
        "search_round": 0,
        "source_selection": SourceSelectionConfig(
            mode=SourceSelectionMode.VERIFIED_ONLY,
            verified_domains={"bbc.com"},
        ),
    }

    result = nodes.search(state)

    assert result["search_results"][0] is original_result

