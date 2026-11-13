
"""Graph state and the structured objects that flow through it."""


from typing import TypedDict

from pydantic import BaseModel, Field

from research_agent.discovery.models import SearchResult
from research_agent.ingestion.acquisition import AcquisitionResult
from research_agent.discovery.source_selection import SourceSelectionConfig

class ResearchPlan(BaseModel):
    """The plan the agent proposes before any searching happens."""

    objective: str = Field(
        description="One-sentence statement of what the report will answer"
    )

    search_queries: list[str] = Field(
        description="3-5 web search queries that together cover the topic",
        min_length=1,
    )

    outline: list[str] = Field(
        description="Section headings the final report should contain",
        min_length=1,
    )


class SourceSelection(BaseModel):
    """LLM's pick of which search results are worth fetching."""

    urls: list[str] = Field(
        description="URLs to fetch, most promising first"
    )

    reasoning: str = Field(
        description="One sentence on why these were chosen"
    )


class AcquiredResource(BaseModel):
    """
    Connects a discovered search result to its acquisition outcome.

    This is a graph execution object, not a domain entity.
    """

    search_result: SearchResult
    acquisition: AcquisitionResult
    attempt_count: int = Field(default=1, ge=1)


class ResearchState(TypedDict, total=False):
    topic: str
    feedback: str

    # Research planning
    plan: dict

    source_selection: SourceSelectionConfig

    # Discovery
    search_results: list[SearchResult]
    search_round: int

    # Acquisition
    acquired_resources: list[AcquiredResource]

    # Final output
    report: str

