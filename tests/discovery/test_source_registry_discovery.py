


from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from research_agent.core.models.source import SourceType
from research_agent.core.persistence.base import Base
from research_agent.core.persistence.models.source import SourceRecord
from research_agent.discovery.source_registry import SourceRegistry


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(engine)

    with Session(engine) as db:
        yield db

    engine.dispose()


def create_source_record(session):
    now = datetime.now(timezone.utc)

    source = SourceRecord(
        id=uuid4(),
        source_type=SourceType.NEWS.value,
        name="Reuters",
        url="https://www.reuters.com",
        domain="reuters.com",
        description="International news organization",
        created_at=now,
        updated_at=now,
    )

    session.add(source)
    session.commit()

    return source


def test_finds_known_source(session):
    expected = create_source_record(session)

    registry = SourceRegistry(session)

    result = registry.find_source_by_url(
        "https://www.reuters.com/world/article"
    )

    assert result is not None
    assert result.id == expected.id
    assert result.name == "Reuters"
    assert result.domain == "reuters.com"


def test_recognizes_www_and_subdomain(session):
    create_source_record(session)

    registry = SourceRegistry(session)

    result = registry.find_source_by_url(
        "https://www.reuters.com/business"
    )

    assert result is not None
    assert result.name == "Reuters"


def test_returns_none_for_unknown_source(session):
    registry = SourceRegistry(session)

    result = registry.find_source_by_url(
        "https://example.com/article"
    )

    assert result is None


def test_does_not_register_unknown_source(session):
    registry = SourceRegistry(session)

    registry.find_source_by_url(
        "https://example.com/article"
    )

    count = session.scalar(
        select(func.count()).select_from(SourceRecord)
    )

    assert count == 0


def test_returns_pydantic_source(session):
    create_source_record(session)

    registry = SourceRegistry(session)

    result = registry.find_source_by_url(
        "https://reuters.com/article"
    )

    from research_agent.core.models.source import Source

    assert isinstance(result, Source)


def test_rejects_invalid_url(session):
    registry = SourceRegistry(session)

    with pytest.raises(ValueError):
        registry.find_source_by_url("not-a-url")

