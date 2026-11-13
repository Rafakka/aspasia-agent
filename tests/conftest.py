
import pytest

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from research_agent.core.persistence.base import Base
from research_agent.core.persistence.models.source import SourceRecord
from research_agent.core.persistence.models.verified_source import (
    VerifiedSourceRecord,
)
from research_agent.core.persistence.repositories.verified_source_registry import (
    VerifiedSourceRegistry,
)


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
def registry(session):
    return VerifiedSourceRegistry(session)


@pytest.fixture
def registry_with_verified_sources(
    session,
    registered_source,
):
    registry = VerifiedSourceRegistry(session)
    registry.add(registered_source.id)
    session.flush()

    return registry

