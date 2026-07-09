"""Web search and page fetching. Pure I/O — no LLM calls here, so each piece is unit-testable."""

import logging

import httpx
import trafilatura
from ddgs import DDGS

from . import config
from .state import SearchResult, Source

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


def fetch_page(url: str, title: str = "") -> Source | None:
    """Download a page and extract its main text. Returns None on any failure."""
    log.info("fetch: %s", url)
    try:
        resp = httpx.get(
            url,
            timeout=config.FETCH_TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (research-agent demo)"},
        )
        resp.raise_for_status()
    except Exception as exc:
        log.warning("fetch failed for %s: %s", url, exc)
        return None
    text = trafilatura.extract(resp.text) or ""
    if len(text) < 200:  # boilerplate-only pages aren't usable evidence
        log.warning("fetch: %s extracted only %d chars, skipping", url, len(text))
        return None
    text = text[: config.MAX_PAGE_CHARS]
    log.info("fetch: %s -> %d chars", url, len(text))
    return Source(title=title or url, url=url, text=text)
