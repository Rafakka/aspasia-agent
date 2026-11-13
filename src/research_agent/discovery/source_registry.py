

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.core.models.source import Source, SourceType
from research_agent.core.persistence.models.source import SourceRecord
from research_agent.discovery.domain import extract_source_domain


class SourceRegistry:

    def __init__(self, session: Session):
        self.session = session

    def find_source_by_url(self, url: str) -> Source | None:
        extracted = extract_source_domain(url)

        statement = select(SourceRecord).where(
            SourceRecord.domain == extracted.registered_domain
        )

        record = self.session.scalar(statement)

        if record is None:
            return None

        return Source(
            id=record.id,
            source_type=SourceType(record.source_type),
            name=record.name,
            url=record.url,
            domain=record.domain,
            description=record.description,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
