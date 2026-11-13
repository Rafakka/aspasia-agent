
import pytest

from research_agent.core.persistence.repositories.verified_source_registry import (
    VerifiedSourceRegistry,
)


def test_add_verified_source(session, registered_source):
    registry = VerifiedSourceRegistry(session)

    registry.add(registered_source.id)
    session.flush()

    assert registry.has_verified_sources()


def test_add_same_source_twice_is_idempotent(
    session,
    registered_source,
):
    registry = VerifiedSourceRegistry(session)

    registry.add(registered_source.id)
    registry.add(registered_source.id)
    session.flush()

    assert registry.list_verified_domains() == {"bbc.com"}


def test_remove_verified_source(session, registered_source):
    registry = VerifiedSourceRegistry(session)

    registry.add(registered_source.id)
    session.flush()

    registry.remove(registered_source.id)
    session.flush()

    assert not registry.has_verified_sources()


def test_list_verified_domains(session, registered_source):
    registry = VerifiedSourceRegistry(session)

    registry.add(registered_source.id)
    session.flush()

    domains = registry.list_verified_domains()

    assert domains == {"bbc.com"}


def test_empty_registry(session):
    registry = VerifiedSourceRegistry(session)

    assert not registry.has_verified_sources()
    assert registry.list_verified_domains() == set()


def test_add_by_domains(session, registered_source):
    registry = VerifiedSourceRegistry(session)

    registry.add_by_domains({"bbc.com"})
    session.flush()

    assert registry.list_verified_domains() == {"bbc.com"}


def test_add_by_domains_rejects_unknown_domain(
    session,
    registered_source,
):
    registry = VerifiedSourceRegistry(session)

    with pytest.raises(ValueError):
        registry.add_by_domains({
            "bbc.com",
            "unknown-example.com",
        })

    assert registry.list_verified_domains() == set()

