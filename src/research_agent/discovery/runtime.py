from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

@dataclass(frozen=True)
class ResearchContext:
    session_factory: sessionmaker[Session]
