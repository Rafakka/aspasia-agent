
import pytest

from research_agent.state import SearchResult

from research_agent.toolkit import filters

from research_agent.toolkit.filters import (
    dedupe_results,
    normalize_source_url,
    extract_source_domain,
)

def _r(url):
    return SearchResult(title=url, url=url)

def test_dedupe_keeps_first_occurrence():
    results = [_r("https://a.com/x"), _r("https://b.com"), _r("https://a.com/x")]
    unique = dedupe_results(results)
    assert [r.url for r in unique] == ["https://a.com/x", "https://b.com"]


def test_dedupe_ignores_trailing_slash():
    results = [_r("https://a.com/x/"), _r("https://a.com/x")]
    assert len(dedupe_results(results)) == 1

def test_normalize_source_url_removes_trailing_slash():
    assert normalize_source_url(
        "https://example.com/"
    ) == "https://example.com"


def test_normalize_source_url_normalizes_hostname():
    assert normalize_source_url(
        "HTTPS://EXAMPLE.COM"
    ) == "https://example.com"


def test_normalize_source_url_removes_fragment():
    assert normalize_source_url(
        "https://example.com/article#section"
    ) == "https://example.com/article"


def test_normalize_source_url_preserves_query_parameters():
    assert normalize_source_url(
        "https://example.com/article?id=10"
    ) == "https://example.com/article?id=10"


def test_normalize_source_url_distinguishes_query_parameters():
    first = normalize_source_url(
        "https://example.com/article?id=10"
    )
    second = normalize_source_url(
        "https://example.com/article?id=20"
    )

    assert first != second

@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://www.historia.com.br/antropologia",
            "historia.com.br",
        ),
        (
            "https://blog.historia.com.br/artigo",
            "historia.com.br",
        ),
        (
            "https://www.bbc.co.uk/news",
            "bbc.co.uk",
        ),
        (
            "https://news.example.com/article",
            "example.com",
        ),
        (
            "http://historia.com.br",
            "historia.com.br",
        ),
    ],
)
def test_extract_source_domain(url, expected):
    assert extract_source_domain(url) == expected

@pytest.mark.parametrize(
    "url",
    [
        "https://localhost:8000",
        "https://com",
        "https://",
    ],
)
def test_extract_source_domain_without_registrable_domain(url):
    assert extract_source_domain(url) == ""


def test_group_results_by_source_domain():
    results = [
        _r("https://historia.com.br/antropologia/artigo-1"),
        _r("https://www.historia.com.br/arqueologia/artigo-2"),
        _r("https://blog.historia.com.br/artigo-3"),
    ]

    grouped = filters.group_results_by_source_domain(results)

    assert len(grouped) == 1
    assert len(grouped["historia.com.br"]) == 3

def test_group_results_by_source_domain_separates_domains():
    results = [
        _r("https://historia.com.br/artigo"),
        _r("https://bbc.co.uk/news"),
        _r("https://example.com/article"),
    ]

    grouped = filters.group_results_by_source_domain(results)

    assert len(grouped) == 3

def test_group_results_by_source_domain_preserves_documents():
    results = [
        _r("https://historia.com.br/artigo-1"),
        _r("https://historia.com.br/artigo-2"),
        _r("https://historia.com.br/artigo-3"),
    ]

    grouped = filters.group_results_by_source_domain(results)

    documents = grouped["historia.com.br"]

    assert len(documents) == 3
    assert [item.url for item in documents] == [
        result.url for result in results
    ]

def test_group_results_by_source_domain_ignores_invalid_domains():
    results = [
        _r("https://historia.com.br/artigo"),
        _r("https://localhost:8000"),
        _r("https://com"),
    ]

    grouped = filters.group_results_by_source_domain(results)

    assert len(grouped) == 1
    assert "historia.com.br" in grouped

