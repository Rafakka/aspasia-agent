


import logging

import trafilatura

from research_agent.config import MAX_PAGE_CHARS

logger = logging.getLogger(__name__)


def extract_html(
    content: bytes,
    url: str | None = None,
) -> str | None:
    """
    Extracts the main readable content from an HTML resource.

    Args:
        content: Original HTML content as bytes.
        url: Original resource URL, used as extraction context.

    Returns:
        Extracted text or None if no readable content is found.

    Raises:
        ValueError: If the supplied content is empty.
        Exception: If the extraction engine fails unexpectedly.
    """

    if not content:
        raise ValueError("Cannot extract content from an empty HTML resource.")

    try:
        html = content.decode("utf-8", errors="replace")

        extracted_text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            include_links=False,
            favor_precision=True,
        )

    except Exception:
        logger.exception(
            "HTML extraction failed for resource: %s",
            url or "unknown URL",
        )
        raise

    if not extracted_text:
        logger.warning(
            "No readable content extracted from resource: %s",
            url or "unknown URL",
        )
        return None

    extracted_text = extracted_text.strip()

    if not extracted_text:
        return None

    if len(extracted_text) > MAX_PAGE_CHARS:
        logger.info(
            "Extracted content truncated from %d to %d characters: %s",
            len(extracted_text),
            MAX_PAGE_CHARS,
            url or "unknown URL",
        )

        extracted_text = extracted_text[:MAX_PAGE_CHARS]

    return extracted_text

