

from research_agent.discovery.source_filter import SourceFilter
from research_agent.discovery.source_selection import (
    SourceSelectionConfig,
    SourceSelectionMode,
)


def test_all_mode_returns_every_result():
    results = [
        {"url": "https://ibge.gov.br/data"},
        {"url": "https://bbc.com/news"},
    ]

    config = SourceSelectionConfig(
        mode=SourceSelectionMode.ALL,
    )

    filtered = SourceFilter.apply(
        results,
        config,
        get_url=lambda result: result["url"],
    )

    assert filtered == results


def test_verified_only_keeps_registered_domains():
    results = [
        {"url": "https://ibge.gov.br/data"},
        {"url": "https://www.inpe.br/research"},
        {"url": "https://bbc.com/news"},
    ]

    config = SourceSelectionConfig(
        mode=SourceSelectionMode.VERIFIED_ONLY,
        verified_domains={"ibge.gov.br", "inpe.br"},
    )

    filtered = SourceFilter.apply(
        results,
        config,
        get_url=lambda result: result["url"],
    )

    assert len(filtered) == 2


def test_verified_only_with_empty_list_returns_all():
    results = [
        {"url": "https://ibge.gov.br/data"},
        {"url": "https://bbc.com/news"},
    ]

    config = SourceSelectionConfig(
        mode=SourceSelectionMode.VERIFIED_ONLY,
        verified_domains=set(),
    )

    filtered = SourceFilter.apply(
        results,
        config,
        get_url=lambda result: result["url"],
    )

    assert filtered == results


def test_filter_preserves_original_result_objects():
    first = {"url": "https://ibge.gov.br/data", "title": "IBGE"}
    second = {"url": "https://bbc.com/news", "title": "BBC"}

    config = SourceSelectionConfig(
        mode=SourceSelectionMode.VERIFIED_ONLY,
        verified_domains={"ibge.gov.br"},
    )

    filtered = SourceFilter.apply(
        [first, second],
        config,
        get_url=lambda result: result["url"],
    )

    assert filtered[0] is first

