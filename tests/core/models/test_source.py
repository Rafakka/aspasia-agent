
from datetime import datetime, timezone
from uuid import UUID

from research_agent.core.models.source import Source, SourceType


def test_source_creation():
    source = Source(
        name="Universidade de São Paulo",
        url="https://www.usp.br",
        domain="usp.br",
        source_type=SourceType.ACADEMIC,
    )

    assert source.name == "Universidade de São Paulo"
    assert source.source_type == SourceType.ACADEMIC


def test_source_generates_uuid():
    source = Source(
        name="USP",
        url="https://www.usp.br",
        domain="usp.br",
        source_type=SourceType.ACADEMIC,
    )

    assert isinstance(source.id, UUID)


def test_source_generates_timestamps():
    source = Source(
        name="USP",
        url="https://www.usp.br",
        domain="usp.br",
        source_type=SourceType.ACADEMIC,
    )

    assert isinstance(source.created_at, datetime)
    assert isinstance(source.updated_at, datetime)
    assert source.created_at.tzinfo == timezone.utc


def test_source_description_is_optional():
    source = Source(
        name="USP",
        url="https://www.usp.br",
        domain="usp.br",
        source_type=SourceType.ACADEMIC,
    )

    assert source.description is None


def test_source_accepts_description():
    source = Source(
        name="USP",
        url="https://www.usp.br",
        domain="usp.br",
        source_type=SourceType.ACADEMIC,
        description="Universidade pública brasileira.",
    )

    assert source.description == "Universidade pública brasileira."


def test_source_type_values():
    assert SourceType.ACADEMIC == "academic"
    assert SourceType.NEWS == "news"
    assert SourceType.SOCIAL_MEDIA == "social_media"
    assert SourceType.GOVERNMENT == "government"
    assert SourceType.ORGANIZATION == "organization"
    assert SourceType.OTHER == "other"

