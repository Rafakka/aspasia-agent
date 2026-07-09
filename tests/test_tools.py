from research_agent.state import SearchResult
from research_agent.tools import dedupe_results


def _r(url):
    return SearchResult(title=url, url=url)


def test_dedupe_keeps_first_occurrence():
    results = [_r("https://a.com/x"), _r("https://b.com"), _r("https://a.com/x")]
    unique = dedupe_results(results)
    assert [r.url for r in unique] == ["https://a.com/x", "https://b.com"]


def test_dedupe_ignores_trailing_slash():
    results = [_r("https://a.com/x/"), _r("https://a.com/x")]
    assert len(dedupe_results(results)) == 1
