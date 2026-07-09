"""Assemble the LangGraph. Run `python -m research_agent.graph` to print the mermaid diagram."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import ResearchState


def build_graph():
    g = StateGraph(ResearchState)

    g.add_node("plan", nodes.plan)
    # destinations documents where the Command node can go, so it renders in the diagram
    g.add_node("approve_plan", nodes.approve_plan, destinations=("plan", "search"))
    g.add_node("search", nodes.search)
    g.add_node("select_sources", nodes.select_sources)
    g.add_node("fetch", nodes.fetch)
    g.add_node("synthesize", nodes.synthesize)

    g.add_edge(START, "plan")
    g.add_edge("plan", "approve_plan")
    # approve_plan routes itself via Command (human decision)
    g.add_edge("search", "select_sources")
    g.add_edge("select_sources", "fetch")
    g.add_conditional_edges("fetch", nodes.route_after_fetch, ["search", "synthesize"])
    g.add_edge("synthesize", END)
    return g


def compile_graph(checkpointer=None):
    # interrupt() requires a checkpointer so the run can pause and resume
    return build_graph().compile(checkpointer=checkpointer or MemorySaver())


if __name__ == "__main__":
    print(compile_graph().get_graph().draw_mermaid())
