

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.core.models.source import Source
from research_agent.core.persistence.models.source import SourceRecord
from research_agent.discovery.domain import extract_source_domain


class SourceRegistry:
    def __init__(self, session: Session):
        self.session = session

    def find_source_by_url(self, url: str) -> Source | None:
        """
        Find a registered source using the URL's normalized domain.
        """
        domain = extract_source_domain(url).registered_domain

        statement = select(SourceRecord).where(
            SourceRecord.domain == domain
        )

        record = self.session.scalar(statement)

        if record is None:
            return None

        return Source(
            id=record.id,
            source_type=record.source_type,
            name=record.name,
            url=record.url,
            domain=record.domain,
            description=record.description,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

