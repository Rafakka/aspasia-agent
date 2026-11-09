"""Web search and page fetching. Pure I/O — no LLM calls here, so each piece is unit-testable."""

import logging

from ddgs import DDGS

from . import config
from .state import SearchResult

log = logging.getLogger("research_agent.tools")


def web_search(query: str, max_results: int | None = None) -> list[SearchResult]:
    """Run one web search query and return normalized results."""
    max_results = max_results or config.MAX_SEARCH_RESULTS
    log.info("search: %r (max %d results)", query, max_results)
    try:
        raw = DDGS().text(query, max_results=max_results)
    except Exception as exc:  # search backends are flaky; a failed query is not fatal
        log.warning("search failed for %r: %s", query, exc)
        return []
    results = []
    for item in raw or []:
        url = item.get("href") or item.get("url") or ""
        if not url:
            continue
        results.append(
            SearchResult(title=item.get("title", url), url=url, snippet=item.get("body", ""))
        )
    log.info("search: %r -> %d results", query, len(results))
    return results


def dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    """Drop duplicate URLs, keeping first occurrence (order = relevance)."""
    seen: set[str] = set()
    unique = []
    for r in results:
        key = r.url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique

