
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from research_agent.discovery.runtime import ResearchContext


def test_research_context_provides_session_factory():
    engine = create_engine("sqlite://")
    factory = sessionmaker(bind=engine)

    context = ResearchContext(session_factory=factory)

    with context.session_factory() as session:
        result = session.execute(text("SELECT 1")).scalar_one()

    assert result == 1

    engine.dispose()
