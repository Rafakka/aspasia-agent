"""Graph nodes. Each node is a plain function over ResearchState, so each can be tested alone."""

import logging

from langgraph.types import Command, interrupt

from . import config, llm, tools
from .state import ResearchPlan, ResearchState, Source, SourceSelection

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
        return {"sources": []}
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
    """Download and extract text from the selected sources."""
    sources: list[Source] = []
    for r in state["search_results"]:
        page = tools.fetch_page(r.url, title=r.title)
        if page:
            sources.append(page)
    log.info("fetch: %d/%d sources fetched successfully", len(sources), len(state["search_results"]))
    return {"sources": state.get("sources", []) + sources}


def route_after_fetch(state: ResearchState) -> str:
    """Branch: enough evidence to write, or go search again (bounded retries)."""
    have = len(state.get("sources", []))
    if have >= config.MIN_SOURCES or state.get("search_round", 0) >= config.MAX_SEARCH_ROUNDS:
        log.info("route: %d sources -> synthesize", have)
        return "synthesize"
    log.info("route: only %d sources (< %d) -> another search round", have, config.MIN_SOURCES)
    return "search"


def synthesize(state: ResearchState) -> dict:
    """Write the final cited markdown report from the fetched sources."""
    sources = state["sources"]
    source_blocks = "\n\n".join(
        f'<source id="{i}" title="{s.title}" url="{s.url}">\n{s.text}\n</source>'
        for i, s in enumerate(sources, start=1)
    )
    outline = "\n".join(f"- {h}" for h in state["plan"]["outline"])
    log.info("synthesize: writing report from %d sources", len(sources))
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
