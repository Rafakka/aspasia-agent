

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from research_agent.core.persistence.base import Base
from research_agent.core.persistence.models.source import SourceRecord

from datetime import datetime, timezone
from uuid import uuid4


@pytest.fixture
def registered_source(session):
    source = SourceRecord(
        id=uuid4(),
        source_type="news",
        name="BBC News",
        url="https://www.bbc.com",
        domain="bbc.com",
        description="International news organization",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    session.add(source)
    session.commit()

    return source


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with TestingSession() as session:
        yield session

    engine.dispose()


from research_agent.core.models.source import Source
from research_agent.core.persistence.models.source_registry import (
    SourceRegistry,
)


def test_find_registered_source(session, registered_source):
    registry = SourceRegistry(session)

    result = registry.find_source_by_url(
        "https://www.bbc.com/news/article"
    )

    assert isinstance(result, Source)
    assert result.id == registered_source.id
    assert result.name == "BBC News"


def test_returns_none_for_unknown_source(session):
    registry = SourceRegistry(session)

    result = registry.find_source_by_url(
        "https://example.com/article"
    )

    assert result is None


def test_recognizes_source_with_different_path(session, registered_source):
    registry = SourceRegistry(session)

    result = registry.find_source_by_url(
        "https://bbc.com/sport/football"
    )

    assert result is not None
    assert result.id == registered_source.id


def test_unknown_source_does_not_create_record(session):
    registry = SourceRegistry(session)

    initial_count = session.query(SourceRecord).count()

    result = registry.find_source_by_url(
        "https://unknown-example.com/article"
    )

    final_count = session.query(SourceRecord).count()

    assert result is None
    assert final_count == initial_count


def test_invalid_url_raises_value_error(session):
    registry = SourceRegistry(session)

    with pytest.raises(ValueError):
        registry.find_source_by_url("ftp://bbc.com")


