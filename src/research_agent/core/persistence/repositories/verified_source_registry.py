
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.core.persistence.models.source import SourceRecord
from research_agent.core.persistence.models.verified_source import (
    VerifiedSourceRecord,
)


class VerifiedSourceRegistry:

    def __init__(self, session: Session):
        self.session = session

    def add(self, source_id: UUID) -> None:
         # Verifica se já existe um registro pendente na sessão.
        pending = any(
            isinstance(record, VerifiedSourceRecord)
            and record.source_id == source_id
            for record in self.session.new
        )

        if pending:
            return

        existing = self.session.get(
            VerifiedSourceRecord,
            source_id,
        )

        if existing is not None:
            return

        record = VerifiedSourceRecord(
            source_id=source_id,
            verified_at=datetime.now(timezone.utc),
        )

        self.session.add(record)

    def remove(self, source_id: UUID) -> None:
        record = self.session.get(
            VerifiedSourceRecord,
            source_id,
        )

        if record is not None:
            self.session.delete(record)

    def list_verified_domains(self) -> set[str]:
        statement = (
            select(SourceRecord.domain)
            .join(
                VerifiedSourceRecord,
                VerifiedSourceRecord.source_id == SourceRecord.id,
            )
        )

        return set(self.session.scalars(statement).all())

    def has_verified_sources(self) -> bool:
        statement = select(VerifiedSourceRecord.source_id).limit(1)

        return self.session.scalar(statement) is not None


    def add_by_domains(self, domains: set[str]) -> None:
        if not domains:
            return

        statement = select(SourceRecord).where(
            SourceRecord.domain.in_(domains)
        )

        sources = self.session.scalars(statement).all()

        found_domains = {source.domain for source in sources}

        missing_domains = domains - found_domains

        if missing_domains:
            raise ValueError(
                f"Sources not registered: {sorted(missing_domains)}"
            )

        for source in sources:
            self.add(source.id)

