


from collections.abc import Callable, Iterable
from typing import TypeVar

from research_agent.discovery.domain import extract_source_domain
from research_agent.discovery.source_selection import (
    SourceSelectionConfig,
    SourceSelectionMode,
)


T = TypeVar("T")


class SourceFilter:

    @staticmethod
    def apply(
        results: Iterable[T],
        config: SourceSelectionConfig,
        get_url: Callable[[T], str],
    ) -> list[T]:

        results = list(results)

        if config.mode == SourceSelectionMode.ALL:
            return results

        if not config.verified_domains:
            return results

        filtered_results = []

        for result in results:
            domain = extract_source_domain(
                get_url(result)
            ).registered_domain

            if domain in config.verified_domains:
                filtered_results.append(result)

        return filtered_results

