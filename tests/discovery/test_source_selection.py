

from research_agent.discovery.source_selection import (
    SourceSelectionConfig,
    SourceSelectionMode,
    resolve_source_selection,
)


def test_all_mode_does_not_require_verified_sources(registry):
    config = resolve_source_selection(
        mode=SourceSelectionMode.ALL,
        registry=registry,
    )

    assert config.mode == SourceSelectionMode.ALL


def test_empty_verified_list_requests_user_selection(registry):
    config = resolve_source_selection(
        mode=SourceSelectionMode.VERIFIED_ONLY,
        registry=registry,
    )

    assert config is None


def test_empty_user_selection_falls_back_to_all(registry):
    config = resolve_source_selection(
        mode=SourceSelectionMode.VERIFIED_ONLY,
        registry=registry,
        selected_domains=set(),
    )

    assert config.mode == SourceSelectionMode.ALL


def test_user_selection_creates_verified_config(registry):
    config = resolve_source_selection(
        mode=SourceSelectionMode.VERIFIED_ONLY,
        registry=registry,
        selected_domains={"ibge.gov.br", "inpe.br"},
    )

    assert config.mode == SourceSelectionMode.VERIFIED_ONLY
    assert config.verified_domains == {
        "ibge.gov.br",
        "inpe.br",
    }


def test_saved_verified_list_takes_precedence(
    registry_with_verified_sources,
):
    config = resolve_source_selection(
        mode=SourceSelectionMode.VERIFIED_ONLY,
        registry=registry_with_verified_sources,
        selected_domains={"bbc.com"},
    )

    assert config.mode == SourceSelectionMode.VERIFIED_ONLY
    assert config.verified_domains == {"bbc.com"}

