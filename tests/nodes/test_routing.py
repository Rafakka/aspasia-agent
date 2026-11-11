
import pytest

from research_agent import config, nodes
from research_agent.state import SearchResult, AcquiredResource
from research_agent.ingestion.acquisition import (
    AcquisitionResult,
    AcquisitionStatus,
)


def test_route_after_fetch_counts_extracted_content(monkeypatch):
    monkeypatch.setattr(config, "MIN_SOURCES", 2)

    results = [
        AcquiredResource(
            search_result=SearchResult(
                title="HTML A",
                url="https://a.com",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Useful extracted content",
            ),
        ),
        AcquiredResource(
            search_result=SearchResult(
                title="PDF",
                url="https://b.com/file.pdf",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.UNSUPPORTED_EXTRACTION,
            ),
        ),
        AcquiredResource(
            search_result=SearchResult(
                title="HTML C",
                url="https://c.com",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="   ",
            ),
        ),
    ]

    result = nodes.route_after_fetch(
        {
            "acquired_resources": results,
            "search_round": 1,
        }
    )

    assert result == "search"


def test_route_after_fetch_synthesizes_with_enough_content(monkeypatch):
    monkeypatch.setattr(config, "MIN_SOURCES", 1)

    results = [
        AcquiredResource(
            search_result=SearchResult(title="A", url="https://a.com"),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Content A",
            ),
        ),
        AcquiredResource(
            search_result=SearchResult(title="B", url="https://b.com"),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.PARTIAL,
                extracted_content="Content B",
            ),
        ),
    ]

    result = nodes.route_after_fetch(
        {
            "acquired_resources": results,
            "search_round": 0,
        }
    )

    assert result == "synthesize"


def test_route_after_fetch_respects_max_search_rounds(monkeypatch):
    monkeypatch.setattr(config, "MIN_SOURCES", 2)
    monkeypatch.setattr(config, "MAX_SEARCH_ROUNDS", 1)

    result = nodes.route_after_fetch(
        {
            "acquired_resources": [],
            "search_round": 1,
        }
    )

    assert result == "synthesize"

@pytest.mark.parametrize(
    "n_sources,search_round,expected",
    [
        (config.MIN_SOURCES, 1, "synthesize"),
        (0, 1, "search"),
        (0, config.MAX_SEARCH_ROUNDS, "synthesize"),
    ],
)
def test_route_after_fetch(n_sources, search_round, expected):
    acquired_resources = [
        AcquiredResource(
            search_result=SearchResult(
                title=f"Source {i}",
                url=f"https://source{i}.com",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Useful extracted content",
            ),
        )
        for i in range(n_sources)
    ]

    state = {
        "acquired_resources": acquired_resources,
        "search_round": search_round,
    }

    assert nodes.route_after_fetch(state) == expected


def test_route_after_fetch_counts_same_domain_as_one_source(monkeypatch):
    monkeypatch.setattr(config, "MIN_SOURCES", 2)

    resources = [
        AcquiredResource(
            search_result=SearchResult(
                title="Artigo 1",
                url="https://historia.com.br/artigo-1",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Conteúdo 1",
            ),
        ),
        AcquiredResource(
            search_result=SearchResult(
                title="Artigo 2",
                url="https://www.historia.com.br/artigo-2",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Conteúdo 2",
            ),
        ),
    ]

    assert nodes.route_after_fetch({
        "acquired_resources": resources,
        "search_round": 1,
    }) == "search"


def test_route_after_fetch_counts_different_domains_separately(monkeypatch):
    monkeypatch.setattr(config, "MIN_SOURCES", 2)

    resources = [
        AcquiredResource(
            search_result=SearchResult(
                title="História",
                url="https://historia.com.br/artigo",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Conteúdo 1",
            ),
        ),
        AcquiredResource(
            search_result=SearchResult(
                title="BBC",
                url="https://bbc.co.uk/news",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Conteúdo 2",
            ),
        ),
    ]

    assert nodes.route_after_fetch({
        "acquired_resources": resources,
        "search_round": 1,
    }) == "synthesize"
