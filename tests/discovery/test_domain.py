import pytest

from research_agent.discovery.domain import extract_source_domain

def test_extracts_simple_domain():
    result = extract_source_domain("https://www.reuters.com/world")

    assert result.hostname == "reuters.com"
    assert result.registered_domain == "reuters.com"
    assert result.subdomain == ""
    assert result.suffix == "com"


def test_extracts_compound_suffix():
    result = extract_source_domain(
        "https://news.example.co.uk/article"
    )

    assert result.hostname == "news.example.co.uk"
    assert result.registered_domain == "example.co.uk"
    assert result.subdomain == "news"
    assert result.suffix == "co.uk"


def test_removes_www():
    result = extract_source_domain(
        "https://www.news.example.com/article"
    )

    assert result.hostname == "news.example.com"
    assert result.subdomain == "news"


def test_normalizes_hostname_case():
    result = extract_source_domain(
        "HTTPS://WWW.EXAMPLE.COM/article"
    )

    assert result.hostname == "example.com"


def test_different_paths_produce_same_domain():
    first = extract_source_domain("https://example.com/article-1")
    second = extract_source_domain("https://example.com/article-2")

    assert first == second


@pytest.mark.parametrize(
    "url",
    [
        "",
        "example.com/article",
        "ftp://example.com",
        "https://",
        "https://127.0.0.1",
        "https://localhost",
        "https://user:password@example.com",
        "https://example.com:invalid",
    ],
)
def test_rejects_invalid_urls(url):
    with pytest.raises(ValueError):
        extract_source_domain(url)


