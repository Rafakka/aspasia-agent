
import tldextract

from ..state import SearchResult
from urllib.parse import urlsplit, urlunsplit

SOURCE_DOMAIN_EXTRACTOR = tldextract.TLDExtract(
    suffix_list_urls=()
)


def normalize_source_url(url: str) -> str:
    """Normalize a URL for source identity comparison."""
    parsed = urlsplit(url.strip())

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def extract_source_domain(url: str) -> str:
    """Extract the registrable domain from a URL."""
    extracted = SOURCE_DOMAIN_EXTRACTOR(url)
    return extracted.top_domain_under_public_suffix

def dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    """Drop duplicate URLs, keeping first occurrence (order = relevance)."""
    seen: set[str] = set()
    unique = []

    for result in results:
        key = normalize_source_url(result.url)

        if key in seen:
            continue

        seen.add(key)
        unique.append(result)

    return unique

def group_results_by_source_domain(
    results: list[SearchResult],
) -> dict[str, list[SearchResult]]:
    """Group search results by their registrable source domain."""
    grouped: dict[str, list[SearchResult]] = {}

    for result in results:
        domain = extract_source_domain(result.url)

        if not domain:
            continue

        grouped.setdefault(domain, []).append(result)

    return grouped
