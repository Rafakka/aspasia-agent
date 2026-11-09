"""Graph nodes. Each node is a plain function over ResearchState, so each can be tested alone."""

import logging

from langgraph.types import Command, interrupt

from . import config, llm, tools

from .ingestion.acquisition import (
    AcquisitionError,
    AcquisitionOptions,
    AcquisitionResult,
    AcquisitionStatus,
    acquire_resource,
)

from .state import (
    AcquiredResource,
    ResearchPlan,
    ResearchState,
    SourceSelection,
)

log = logging.getLogger("research_agent.nodes")

PLAN_PROMPT = """You are a research planner. Produce a research plan for this topic:

<topic>
{topic}
</topic>
{feedback_block}
Design 3-5 web search queries that together cover the topic from complementary angles
(definitions/background, current state, data or evidence, criticism or open questions),
and an outline of 4-6 section headings for the final report."""

SELECT_PROMPT = """You are selecting sources for a research report.

Objective: {objective}

Candidate search results:
{candidates}

Pick the {max_sources} URLs most likely to contain substantive, citable information.
Prefer primary sources, documentation, and in-depth articles over thin listicles or
SEO pages. Avoid picking two URLs from the same site unless clearly warranted."""

SYNTHESIZE_PROMPT = """Write a research report in markdown on the topic below, using ONLY the
provided sources as evidence.

<topic>
{topic}
</topic>

Objective: {objective}

Follow this outline (adjust wording, keep the structure):
{outline}

<sources>
{sources}
</sources>

Requirements:
- Start with a `# <title>` heading and a 3-4 sentence executive summary.
- Cite claims inline with bracketed source numbers, e.g. [1] or [2][3].
- If sources disagree or evidence is thin, say so explicitly — do not paper over gaps.
- End with a `## Sources` section listing each source as `[n] Title — URL`.
- Do not invent facts that are not in the sources."""


def plan(state: ResearchState) -> dict:
    """Draft (or, with human feedback, redraft) the research plan."""
    feedback = state.get("feedback", "")
    feedback_block = (
        f"\nA human reviewer rejected the previous plan with this feedback — address it:\n"
        f"<feedback>\n{feedback}\n</feedback>\n"
        if feedback
        else ""
    )
    log.info("plan: drafting plan for topic %r%s", state["topic"], " (revision)" if feedback else "")
    planner = llm.get_llm().with_structured_output(ResearchPlan)
    research_plan = planner.invoke(
        PLAN_PROMPT.format(topic=state["topic"], feedback_block=feedback_block)
    )
    log.info("plan: objective=%r queries=%s", research_plan.objective, research_plan.search_queries)
    # stored as a plain dict so checkpointed state stays serializer-friendly
    return {"plan": research_plan.model_dump(), "feedback": ""}


def approve_plan(state: ResearchState) -> Command:
    """Human-in-the-loop gate: pause the graph until a person approves the plan.

    interrupt() checkpoints the run and surfaces the payload to the caller;
    the graph resumes only when the caller sends Command(resume=<decision>).
    """
    decision = interrupt(
        {
            "question": "Approve this research plan?",
            "plan": state["plan"],
        }
    )
    if isinstance(decision, dict) and decision.get("action") == "revise":
        log.info("approve_plan: human requested revision: %r", decision.get("feedback", ""))
        return Command(goto="plan", update={"feedback": decision.get("feedback", "")})
    log.info("approve_plan: plan approved by human")
    return Command(goto="search")


def search(state: ResearchState) -> dict:
    """Run every planned query; on a retry round, broaden the queries."""
    round_num = state.get("search_round", 0) + 1
    queries = list(state["plan"]["search_queries"])
    if round_num > 1:
        # Coverage came up short — broaden rather than repeat verbatim.
        queries = [f"{state['topic']} overview", f"{state['topic']} analysis"] + queries
        log.info("search: round %d, broadened to %d queries", round_num, len(queries))
    results = []
    for q in queries:
        results.extend(tools.web_search(q))
    unique = tools.dedupe_results(results)
    log.info("search: round %d collected %d unique results", round_num, len(unique))
    return {"search_results": unique, "search_round": round_num}


def select_sources(state: ResearchState) -> dict:
    """LLM triage: pick which search results are worth fetching."""
    candidates = state["search_results"]
    if not candidates:
        return {"search_results": []}
    listing = "\n".join(f"- {r.title}\n  {r.url}\n  {r.snippet}" for r in candidates[:40])
    selector = llm.get_llm().with_structured_output(SourceSelection)
    selection = selector.invoke(
        SELECT_PROMPT.format(
            objective=state["plan"]["objective"],
            candidates=listing,
            max_sources=config.MAX_SOURCES,
        )
    )
    log.info("select_sources: %s", selection.reasoning)
    by_url = {r.url: r for r in candidates}
    chosen = [by_url[u] for u in selection.urls if u in by_url][: config.MAX_SOURCES]
    log.info("select_sources: fetching %d of %d candidates", len(chosen), len(candidates))
    return {"search_results": chosen}


def fetch(state: ResearchState) -> dict:
    """
    Acquires selected resources and accumulates their outcomes.

    Each search result is processed independently, so an unexpected
    acquisition error does not interrupt the remaining resources.
    """
    search_results = state.get("search_results", [])
    acquired_resources: list[AcquiredResource] = []

    options = AcquisitionOptions(
        store_original=True,
        extract_content=True,
    )

    for result in search_results:
        try:
            acquisition = acquire_resource(
                search_result=result,
                options=options,
            )

        except Exception as exc:
            log.exception(
                "Unexpected acquisition error for %s",
                result.url,
            )

            acquisition = AcquisitionResult(
                status=AcquisitionStatus.FAILED,
                error=AcquisitionError(
                    code="UNEXPECTED_ACQUISITION_ERROR",
                    message=str(exc),
                ),
            )

        acquired_resources.append(
            AcquiredResource(
                search_result=result,
                acquisition=acquisition,
            )
        )

        log.info(
            "fetch: %s -> %s",
            result.url,
            acquisition.status.value,
        )

    # Preserve resources acquired in previous search rounds.
    previous_resources = state.get("acquired_resources", [])
    accumulated_resources = previous_resources + acquired_resources

    log.info(
        "fetch: acquired %d resources in this round; %d accumulated",
        len(acquired_resources),
        len(accumulated_resources),
    )

    return {
        "acquired_resources": accumulated_resources,
    }


def route_after_fetch(state: ResearchState) -> str:
    """Branch based on usable extracted content, or search again."""
    acquired_resources = state.get("acquired_resources", [])

    usable_resources = [
        item
        for item in acquired_resources
        if (
            item.acquisition.extracted_content
            and item.acquisition.extracted_content.strip()
        )
    ]

    have = len(usable_resources)

    if (
        have >= config.MIN_SOURCES
        or state.get("search_round", 0) >= config.MAX_SEARCH_ROUNDS
    ):
        log.info("route: %d usable sources -> synthesize", have)
        return "synthesize"

    log.info(
        "route: only %d usable sources (< %d) -> another search round",
        have,
        config.MIN_SOURCES,
    )
    return "search"



def synthesize(state: ResearchState) -> dict:
    """Write the final cited markdown report from acquired resources."""

    usable_resources = [
        item
        for item in state.get("acquired_resources", [])
        if (
            item.acquisition.extracted_content
            and item.acquisition.extracted_content.strip()
        )
    ]

    if not usable_resources:
        log.warning("synthesize: no usable resources available")
        return {
            "report": "zero recursos, favor consultar busca de fontes"
        }

    source_blocks = "\n\n".join(
        (
            f'<source id="{i}" title="{item.search_result.title}" '
            f'url="{item.search_result.url}">\n'
            f'{item.acquisition.extracted_content}\n'
            f'</source>'
        )
        for i, item in enumerate(usable_resources, start=1)
    )

    outline = "\n".join(
        f"- {heading}" for heading in state["plan"]["outline"]
    )

    log.info(
        "synthesize: writing report from %d usable resources",
        len(usable_resources),
    )

    response = llm.get_llm().invoke(
        SYNTHESIZE_PROMPT.format(
            topic=state["topic"],
            objective=state["plan"]["objective"],
            outline=outline,
            sources=source_blocks,
        )
    )

    usage = getattr(response, "usage_metadata", None)

    if usage:
        log.info(
            "synthesize: done (input_tokens=%s output_tokens=%s)",
            usage.get("input_tokens"),
            usage.get("output_tokens"),
        )

    return {"report": response.text}

