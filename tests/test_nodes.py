"""Node-level tests: every node is exercised in isolation with stubbed LLM/network calls."""

import pytest

from research_agent import config, nodes
from research_agent.state import ResearchPlan, SearchResult, Source, SourceSelection


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


def test_plan_node_returns_plan_and_clears_feedback(monkeypatch):
    stub = StubLLM(ResearchPlan.model_validate(PLAN))
    monkeypatch.setattr(nodes.llm, "get_llm", lambda **kw: stub)
    out = nodes.plan({"topic": "X", "feedback": "too narrow"})
    assert out["plan"] == PLAN
    assert out["feedback"] == ""
    # human feedback must actually reach the prompt on a revision pass
    assert "too narrow" in stub.prompts[0]


def test_search_broadens_queries_on_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(nodes.tools, "web_search", lambda q, **kw: calls.append(q) or [])
    nodes.search({"topic": "X", "plan": PLAN, "search_round": 1})
    assert "X overview" in calls  # round 2 adds broadened queries
    assert "x basics" in calls


def test_select_sources_drops_hallucinated_urls(monkeypatch):
    candidates = [SearchResult(title="A", url="https://a.com"), SearchResult(title="B", url="https://b.com")]
    selection = SourceSelection(urls=["https://a.com", "https://fake.invalid"], reasoning="test")
    monkeypatch.setattr(nodes.llm, "get_llm", lambda **kw: StubLLM(selection))
    out = nodes.select_sources({"plan": PLAN, "search_results": candidates})
    assert [r.url for r in out["search_results"]] == ["https://a.com"]


def test_fetch_skips_failed_pages(monkeypatch):
    def fake_fetch(url, title=""):
        return Source(title=title, url=url, text="x" * 300) if "good" in url else None

    monkeypatch.setattr(nodes.tools, "fetch_page", fake_fetch)
    out = nodes.fetch(
        {"search_results": [SearchResult(title="g", url="https://good.com"),
                            SearchResult(title="b", url="https://bad.com")]}
    )
    assert len(out["sources"]) == 1


@pytest.mark.parametrize(
    "n_sources,search_round,expected",
    [
        (config.MIN_SOURCES, 1, "synthesize"),        # enough evidence -> write
        (0, 1, "search"),                             # not enough -> retry
        (0, config.MAX_SEARCH_ROUNDS, "synthesize"),  # retries exhausted -> write anyway
    ],
)
def test_route_after_fetch(n_sources, search_round, expected):
    state = {
        "sources": [Source(title="t", url="u", text="x") for _ in range(n_sources)],
        "search_round": search_round,
    }
    assert nodes.route_after_fetch(state) == expected
