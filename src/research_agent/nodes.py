"""Graph nodes. Each node is a plain function over ResearchState, so each can be tested alone."""

import logging

from time import perf_counter

from langgraph.runtime import Runtime

from langgraph.types import Command, interrupt

from concurrent.futures import ThreadPoolExecutor

from research_agent.discovery.runtime import ResearchContext

from research_agent.discovery.source_filter import SourceFilter

from research_agent.discovery.source_selection import (
        SourceSelectionConfig,
        SourceSelectionMode,
        )

from research_agent.discovery.fetcher import fetch_resources

from research_agent.core.persistence.repositories.verified_source_registry import (
        VerifiedSourceRegistry,
        )

from . import config, llm
from .toolkit import filters, search as search_tool

from .state import (
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

LANGUAGE REQUIREMENTS:
- Identify the language used in the user's original topic.
- Write the research objective in that language.
- Generate all search queries in that language.
- Write all report outline headings in that language.
- Preserve proper nouns and technical terminology.
- Do not translate the user's topic unless necessary.

RESEARCH PLANNING REQUIREMENTS:
- Design 3-5 web search queries.
- Cover complementary angles:
  definitions and background, historical context, current state,
  data or evidence, criticism and open questions.
- Avoid redundant queries.
- Prefer specific search terms over unnecessarily long questions.
- Consider terminology commonly used in the topic's original language.

Produce an objective, search queries, and an outline of 4-6 section headings."""

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
            "type": "plan_approval",
            "plan": state["plan"],
        }
    )
    if isinstance(decision, dict) and decision.get("action") == "revise":
        log.info("approve_plan: human requested revision: %r", decision.get("feedback", ""))
        return Command(goto="plan", update={"feedback": decision.get("feedback", "")})
    log.info("approve_plan: plan approved by human")
    return Command(goto="configure_sources")


def configure_sources(
    state: ResearchState,
    runtime: Runtime[ResearchContext],
) -> dict:
    """Configure whether research should use the verified source catalog."""

    with runtime.context.session_factory() as session:
        registry = VerifiedSourceRegistry(session)
        verified_domains = registry.list_verified_domains()

    decision = interrupt(
        {
            "type": "source_configuration",
            "question": (
                "Do you want to restrict research to your "
                "pre-approved sources?"
            ),
            "verified_source_count": len(verified_domains),
        }
    )

    if decision is False:
        log.info("configure_sources: searching all sources")
        return {
            "source_selection": SourceSelectionConfig(
                mode=SourceSelectionMode.ALL
            )
        }

    if decision is not True:
        raise ValueError("Invalid source configuration decision.")

    if not verified_domains:
        log.warning(
            "configure_sources: verified source list is empty; "
            "searching all sources"
        )
        return {
            "source_selection": SourceSelectionConfig(
                mode=SourceSelectionMode.ALL
            )
        }

    log.info(
        "configure_sources: restricting search to %d verified domains",
        len(verified_domains),
    )

    return {
        "source_selection": SourceSelectionConfig(
            mode=SourceSelectionMode.VERIFIED_ONLY,
            verified_domains=verified_domains,
        )
    }


def search(state: ResearchState) -> dict:
    round_num = state.get("search_round", 0) + 1
    queries = list(state["plan"]["search_queries"])

    if round_num > 1:
        queries = [
            f"{state['topic']} overview",
            f"{state['topic']} analysis",
        ] + queries

        log.info(
            "search: broadening queries for round %d",
            round_num,
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        batches = list(
            executor.map(search_tool.web_search, queries)
        )

    results = [
        result
        for batch in batches
        for result in batch
    ]

    # 1. Remove resultados duplicados
    unique = filters.dedupe_results(results)

    # 2. Recupera a configuração de seleção de fontes
    # Se ela não existir, utiliza ALL como padrão.
    source_selection = state.get("source_selection")

    if source_selection is None:
        source_selection = SourceSelectionConfig(
            mode=SourceSelectionMode.ALL
        )

    # 3. Aplica a política de seleção de fontes
    filtered = SourceFilter.apply(
        results=unique,
        config=source_selection,
        get_url=lambda result: result.url,
    )

    log.info(
        "search: round %d collected %d unique results, "
        "%d remaining after source filtering",
        round_num,
        len(unique),
        len(filtered),
    )

    return {
        "search_results": filtered,
        "search_round": round_num,
    }

def select_sources(state: ResearchState) -> dict:
    """LLM triage: pick which search results are worth fetching."""
    candidates = state["search_results"]
    if not candidates:
        return {"search_results": []}
    listing = "\n".join(f"- {r.title}\n  {r.url}\n  {r.snippet}" for r in candidates[:40])

    selector = llm.get_llm().with_structured_output(SourceSelection)

    prompt = SELECT_PROMPT.format(
        objective=state["plan"]["objective"],
        candidates=listing,
        max_sources=config.MAX_SOURCES,
    )

    log.info(
        "select_sources: sending %d candidates, %d characters to LLM",
        min(len(candidates), 40),
        len(prompt),
    )

    started_at = perf_counter()

    selection = selector.invoke(prompt)

    elapsed = perf_counter() - started_at

    log.info(
        "select_sources: LLM completed in %.2f seconds",
        elapsed,
    )

    by_url = {r.url: r for r in candidates}
    chosen = [by_url[u] for u in selection.urls if u in by_url][: config.MAX_SOURCES]
    log.info("select_sources: fetching %d of %d candidates", len(chosen), len(candidates))
    return {"search_results": chosen}


def fetch(state: ResearchState) -> dict:
    acquired_resources = fetch_resources(
        search_results=state.get("search_results", []),
        acquired_resources=state.get("acquired_resources", []),
    )

    return {
        "acquired_resources": acquired_resources,
    }

def route_after_fetch(state: ResearchState) -> str:
    """Branch based on unique usable sources, or search again."""

    acquired_resources = state.get("acquired_resources", [])

    usable_results = [
        discovery
        for item in acquired_resources
        if (
            item.acquisition.extracted_content
            and item.acquisition.extracted_content.strip()
        )
        for discovery in item.discoveries
    ]

    unique_results = filters.dedupe_results(usable_results)

    grouped_sources = filters.group_results_by_source_domain(
        unique_results
    )

    have = len(grouped_sources)

    if (
        have >= config.MIN_SOURCES
        or state.get("search_round", 0) >= config.MAX_SEARCH_ROUNDS
    ):
        log.info("route: %d unique usable sources -> synthesize", have)
        return "synthesize"

    log.info(
        "route: only %d unique usable sources (< %d) -> another search round",
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
            f'<source id="{i}">\n'
            f'<discoveries>\n'
            + "\n".join(
                f'<discovery title="{discovery.title}" '
                f'url="{discovery.url}" />'
                for discovery in item.discoveries
            )
            + '\n</discoveries>\n'
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

