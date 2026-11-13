
from types import SimpleNamespace

import pytest

from sqlalchemy.orm import sessionmaker

from research_agent import nodes
from research_agent.discovery.runtime import ResearchContext
from research_agent.discovery.source_selection import (
    SourceSelectionMode,
)


@pytest.fixture
def runtime(session):
    factory = sessionmaker(
        bind=session.get_bind(),
        autoflush=False,
        expire_on_commit=False,
    )

    return SimpleNamespace(
        context=ResearchContext(session_factory=factory)
    )


def test_configure_sources_uses_verified_catalog(
    runtime,
    session,
    registry_with_verified_sources,
    monkeypatch,
):
    session.commit()

    monkeypatch.setattr(
        nodes,
        "interrupt",
        lambda payload: True,
    )

    result = nodes.configure_sources({}, runtime)

    selection = result["source_selection"]

    assert selection.mode == SourceSelectionMode.VERIFIED_ONLY
    assert selection.verified_domains == {"bbc.com"}


def test_configure_sources_uses_all_when_user_declines(
    runtime,
    session,
    registry_with_verified_sources,
    monkeypatch,
):
    session.commit()

    monkeypatch.setattr(
        nodes,
        "interrupt",
        lambda payload: False,
    )

    result = nodes.configure_sources({}, runtime)

    selection = result["source_selection"]

    assert selection.mode == SourceSelectionMode.ALL


def test_configure_sources_falls_back_to_all_when_catalog_is_empty(
    runtime,
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(
        nodes,
        "interrupt",
        lambda payload: True,
    )

    result = nodes.configure_sources({}, runtime)

    selection = result["source_selection"]

    assert selection.mode == SourceSelectionMode.ALL
    assert "list" in caplog.text.lower()

