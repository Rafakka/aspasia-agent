

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResourceType(StrEnum):
    HTML = "html"
    PDF = "pdf"
    SPREADSHEET = "spreadsheet"
    IMAGE = "image"
    OTHER = "other"


class Resource(BaseModel):
    """
    Represents a digital resource discovered or acquired by Aspásia.
    """

    id: UUID = Field(default_factory=uuid4)

    source_id: UUID | None = None

    url: str
    resource_type: ResourceType

    mime_type: str | None = None
    content_hash: str | None = None
    storage_path: str | None = None

    acquired_at: datetime | None = None

    created_at: datetime = Field(default_factory=utc_now)

