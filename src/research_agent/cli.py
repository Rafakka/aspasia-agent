"""CLI entry point: `research-agent "your topic"` (or `python -m research_agent "your topic"`).

Drives the graph, handles the human-approval interrupt at the terminal, and writes
the finished report to reports/.
"""

import argparse
import logging
import re
import sys
import uuid
from pathlib import Path

from langgraph.types import Command

from .graph import compile_graph
from .tracing import setup_tracing

log = logging.getLogger("research_agent.cli")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "report"


def _print_plan(plan: dict) -> None:
    print("\n=== Proposed research plan ===")
    print(f"Objective: {plan['objective']}\n")
    print("Search queries:")
    for q in plan["search_queries"]:
        print(f"  - {q}")
    print("\nReport outline:")
    for h in plan["outline"]:
        print(f"  - {h}")
    print()


def _ask_approval(plan: dict, auto: bool) -> dict:
    """Terminal UI for the approval gate. Returns the resume payload for the graph."""
    _print_plan(plan)
    if auto:
        print("(--auto: plan approved automatically)")
        return {"action": "approve"}
    while True:
        answer = input("Approve plan? [y = approve / r = revise / q = quit] ").strip().lower()
        if answer in ("y", "yes"):
            return {"action": "approve"}
        if answer in ("r", "revise"):
            feedback = input("What should change? ").strip()
            return {"action": "revise", "feedback": feedback}
        if answer in ("q", "quit"):
            print("Aborted before any searching happened.")
            sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Research a topic and write a cited report.")
    parser.add_argument("topic", help="What to research")
    parser.add_argument("--auto", action="store_true", help="Skip the human approval gate")
    parser.add_argument("--out-dir", default="reports", help="Where to write the report")
    args = parser.parse_args()

    trace_path = setup_tracing()
    log.info("run start: topic=%r auto=%s", args.topic, args.auto)

    app = compile_graph()
    run_config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    result = app.invoke({"topic": args.topic}, run_config)
    # interrupt() pauses here — loop until the human approves and the run completes
    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        decision = _ask_approval(payload["plan"], args.auto)
        result = app.invoke(Command(resume=decision), run_config)

    report = result.get("report", "")
    if not report:
        log.error("run ended without a report — see trace: %s", trace_path)
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"report-{_slugify(args.topic)}.md"
    out_path.write_text(report, encoding="utf-8")

    log.info("run complete: report=%s sources=%d", out_path, len(result.get("sources", [])))
    print(f"\nReport written to {out_path}")
    print(f"Full trace at {trace_path}")


if __name__ == "__main__":
    main()
