
from datetime import datetime, timezone

import pytest

from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.orm import sessionmaker

from research_agent import nodes
from research_agent.core.persistence.repositories.verified_source_registry import (
    VerifiedSourceRegistry,
)
from research_agent.discovery.models import SearchResult
from research_agent.discovery.runtime import ResearchContext
from research_agent.graph import build_graph


PLAN = {
    "objective": "Explain X",
    "search_queries": ["X overview"],
    "outline": ["Background", "Findings"],
}


@pytest.mark.parametrize(
    "use_verified, populate_catalog, expected_urls",
    [
        (
            True,
            True,
            {"https://www.bbc.com/news/example"},
        ),
        (
            False,
            True,
            {
                "https://www.bbc.com/news/example",
                "https://www.nytimes.com/article/example",
            },
        ),
        (
            True,
            False,
            {
                "https://www.bbc.com/news/example",
                "https://www.nytimes.com/article/example",
            },
        ),
    ],
    ids=[
        "verified-only",
        "user-selects-all",
        "empty-catalog-fallback",
    ],
)
def test_source_selection_flow(
    monkeypatch,
    session,
    registered_source,
    use_verified,
    populate_catalog,
    expected_urls,
):
    # ---------------------------------------------------------
    # 1. Prepare persistent source catalog
    # ---------------------------------------------------------

    if populate_catalog:
        registry = VerifiedSourceRegistry(session)
        registry.add(registered_source.id)
        session.commit()

    session_factory = sessionmaker(
        bind=session.get_bind(),
        autoflush=False,
        expire_on_commit=False,
    )

    context = ResearchContext(
        session_factory=session_factory,
    )

    # ---------------------------------------------------------
    # 2. Prepare deterministic search results
    # ---------------------------------------------------------

    search_results = [
        SearchResult(
            title="BBC article",
            url="https://www.bbc.com/news/example",
            snippet="BBC search result",
        ),
        SearchResult(
            title="New York Times article",
            url="https://www.nytimes.com/article/example",
            snippet="NYT search result",
        ),
    ]

    search_calls = []

    def fake_web_search(query, **kwargs):
        search_calls.append(query)
        return search_results

    monkeypatch.setattr(
        nodes.search_tool,
        "web_search",
        fake_web_search,
    )

    # ---------------------------------------------------------
    # 3. Replace unrelated LLM and acquisition operations
    # ---------------------------------------------------------

    monkeypatch.setattr(
        nodes,
        "plan",
        lambda state: {
            "plan": PLAN,
            "feedback": "",
        },
    )

    selected_candidates = []

    def capture_selected_candidates(state):
        selected_candidates.extend(state["search_results"])
        return {}

    monkeypatch.setattr(
        nodes,
        "select_sources",
        capture_selected_candidates,
    )

    monkeypatch.setattr(
        nodes,
        "fetch",
        lambda state: {"acquired_resources": []},
    )

    monkeypatch.setattr(
        nodes,
        "route_after_fetch",
        lambda state: "synthesize",
    )

    monkeypatch.setattr(
        nodes,
        "synthesize",
        lambda state: {"report": "integration-test-completed"},
    )

    # ---------------------------------------------------------
    # 4. Compile and start the real graph
    # ---------------------------------------------------------

    app = build_graph().compile(
        checkpointer=MemorySaver(),
    )

    run_config = {
        "configurable": {
            "thread_id": "source-selection-integration-test",
        }
    }

    result = app.invoke(
        {"topic": "X"},
        run_config,
        context=context,
    )

    # ---------------------------------------------------------
    # 5. First human interruption: approve research plan
    # ---------------------------------------------------------

    assert "__interrupt__" in result

    plan_interrupt = result["__interrupt__"][0].value

    assert plan_interrupt["type"] == "plan_approval"
    assert plan_interrupt["plan"] == PLAN

    result = app.invoke(
        Command(resume=True),
        run_config,
        context=context,
    )

    # ---------------------------------------------------------
    # 6. Second human interruption: configure source selection
    # ---------------------------------------------------------

    assert "__interrupt__" in result

    source_interrupt = result["__interrupt__"][0].value

    assert source_interrupt["type"] == "source_configuration"

    expected_catalog_count = 1 if populate_catalog else 0

    assert (
        source_interrupt["verified_source_count"]
        == expected_catalog_count
    )

    assert "pre-approved sources" in source_interrupt["question"]

    # ---------------------------------------------------------
    # 7. Resume graph with user's source-selection decision
    # ---------------------------------------------------------

    result = app.invoke(
        Command(resume=use_verified),
        run_config,
        context=context,
    )

    # ---------------------------------------------------------
    # 8. Verify complete execution
    # ---------------------------------------------------------

    assert "__interrupt__" not in result

    assert result["report"] == "integration-test-completed"

    assert len(search_calls) == 1
    assert search_calls == ["X overview"]

    actual_urls = {
        result.url
        for result in selected_candidates
    }

    assert actual_urls == expected_urls

    # The search result list must contain only the expected
    # candidates when it reaches the next graph node.
    assert len(selected_candidates) == len(expected_urls)

