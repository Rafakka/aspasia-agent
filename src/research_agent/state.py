"""Graph state and the structured objects that flow through it."""

from typing import TypedDict

from pydantic import BaseModel, Field


class ResearchPlan(BaseModel):
    """The plan the agent proposes before any searching happens."""

    objective: str = Field(description="One-sentence statement of what the report will answer")
    search_queries: list[str] = Field(
        description="3-5 web search queries that together cover the topic", min_length=1
    )
    outline: list[str] = Field(
        description="Section headings the final report should contain", min_length=1
    )


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""


class SourceSelection(BaseModel):
    """LLM's pick of which search results are worth fetching."""

    urls: list[str] = Field(description="URLs to fetch, most promising first")
    reasoning: str = Field(description="One sentence on why these were chosen")


class Source(BaseModel):
    """A fetched and text-extracted web page."""

    title: str
    url: str
    text: str


class ResearchState(TypedDict, total=False):
    topic: str
    feedback: str  # human feedback when a plan is sent back for revision
    plan: dict  # ResearchPlan.model_dump() — plain dict keeps checkpoints serializer-friendly
    search_results: list[SearchResult]
    sources: list[Source]
    search_round: int
    report: str
