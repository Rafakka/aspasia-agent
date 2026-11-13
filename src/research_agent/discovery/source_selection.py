

from enum import StrEnum

from pydantic import BaseModel, Field

from research_agent.core.persistence.repositories.verified_source_registry import (
    VerifiedSourceRegistry,
)


class SourceSelectionMode(StrEnum):
    VERIFIED_ONLY = "verified_only"
    ALL = "all"


class SourceSelectionConfig(BaseModel):
    mode: SourceSelectionMode = SourceSelectionMode.ALL
    verified_domains: set[str] = Field(default_factory=set)

def resolve_source_selection(
    mode: SourceSelectionMode,
    registry: VerifiedSourceRegistry,
    selected_domains: set[str] | None = None,
) -> SourceSelectionConfig | None:

    if mode == SourceSelectionMode.ALL:
        return SourceSelectionConfig(
            mode=SourceSelectionMode.ALL,
        )

    saved_domains = registry.list_verified_domains()

    if saved_domains:
        return SourceSelectionConfig(
            mode=SourceSelectionMode.VERIFIED_ONLY,
            verified_domains=saved_domains,
        )

    # None significa que ainda precisamos perguntar ao usuário.
    if selected_domains is None:
        return None

    # Se o usuário não selecionar nenhuma fonte,
    # a pesquisa será realizada sem restrições.
    if not selected_domains:
        return SourceSelectionConfig(
            mode=SourceSelectionMode.ALL,
        )

    return SourceSelectionConfig(
        mode=SourceSelectionMode.VERIFIED_ONLY,
        verified_domains=selected_domains,
    )

