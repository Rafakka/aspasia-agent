

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class SourceType(StrEnum):
    ACADEMIC = "academic"
    SOCIAL_MEDIA = "social_media"
    GOVERNMENT = "government"
    ORGANIZATION = "organization"
    NEWS = "news"
    OTHER = "other"

class Source(BaseModel):

    id: UUID = Field(default_factory=uuid4)

    source_type: SourceType

    name: str
    url: str
    domain: str

    description: str | None = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

