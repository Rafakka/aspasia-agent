
import logging

from ddgs import DDGS

from .. import config
from ..state import SearchResult

log = logging.getLogger("research_agent.toolkit.search")


def web_search(query: str, max_results: int | None = None) -> list[SearchResult]:
    """Run one web search query and return normalized results."""
    max_results = max_results or config.MAX_SEARCH_RESULTS
    log.info("search: %r (max %d results)", query, max_results)

    try:
        raw = DDGS().text(query, max_results=max_results)
    except Exception as exc:
        log.warning("search failed for %r: %s", query, exc)
        return []

    results = []

    for item in raw or []:
        url = item.get("href") or item.get("url") or ""

        if not url:
            continue

        results.append(
            SearchResult(
                title=item.get("title", url),
                url=url,
                snippet=item.get("body", ""),
            )
        )

    log.info("search: %r -> %d results", query, len(results))
    return results


