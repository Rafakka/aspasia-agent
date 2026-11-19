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
import itertools
import sys
import threading

from langgraph.types import Command

from .database import SessionLocal
from .graph import compile_graph
from .tracing import setup_tracing

from research_agent.discovery.runtime import ResearchContext

log = logging.getLogger("research_agent.cli")

class Spinner:
    def __init__(self, message: str):
        self.message = message
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        frames = itertools.cycle(["|", "/", "-", "\\"])

        while not self.stop_event.is_set():
            frame = next(frames)
            sys.stdout.write(f"\r[{frame}] {self.message}")
            sys.stdout.flush()
            self.stop_event.wait(0.1)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()

def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "report"

def _ask_source_configuration(
    verified_source_count: int,
    auto: bool,
) -> bool:
    """Ask whether research should use only pre-approved sources."""

    if auto:
        print("(--auto: searching all sources)")
        return False

    if verified_source_count == 0:
        print(
            "No pre-approved sources registered. "
            "Searching all sources."
        )
        return False

    while True:
        answer = input(
            f"Restrict research to your {verified_source_count} "
            "pre-approved sources? [y = yes / n = no / q = quit] "
        ).strip().lower()

        if answer in ("y", "yes"):
            return True

        if answer in ("n", "no"):
            return False

        if answer in ("q", "quit"):
            print("Research aborted.")
            sys.exit(0)

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

def _stream_graph(app, input_data, run_config, context):
    result = None
    interrupts = None
    spinner = None

    try:
        for mode, chunk in app.stream(
            input_data,
            run_config,
            context=context,
            stream_mode=["updates", "values", "custom"],
        ):
            if mode == "updates":
                for node, update in chunk.items():
                    if node == "__interrupt__":
                        interrupts = update
                        print("[GRAPH] Human interruption")
                        continue

                    print(f"[GRAPH] Node completed: {node}")

            elif mode == "values":
                result = chunk

            elif mode == "custom":
                event = chunk.get("event")

                if event == "operation_started":
                    operation = chunk["operation"]

                    if spinner is not None:
                        spinner.stop()

                    spinner = Spinner(f"{operation} processing...")
                    spinner.start()

                elif event == "operation_finished":
                    if spinner is not None:
                        spinner.stop()
                        spinner = None

                    status = chunk["status"]
                    duration = chunk["duration"]
                    operation = chunk["operation"]

                    print(
                        f"[LLM] {operation} {status} "
                        f"| duration={duration:.2f}s"
                    )

    finally:
        if spinner is not None:
            spinner.stop()

    if result is None:
        result = {}

    if interrupts is not None:
        result["__interrupt__"] = interrupts

    return result

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

    context = ResearchContext(session_factory=SessionLocal)

    result = _stream_graph(
            app,
            {"topic":args.topic},
            run_config,
            context,
            )

    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value

        interrupt_type = payload.get("type")

        if interrupt_type == "source_configuration":
            decision = _ask_source_configuration(
                verified_source_count=payload["verified_source_count"],
                auto=args.auto,
            )

        elif "plan" in payload:
            decision = _ask_approval(
                plan=payload["plan"],
                auto=args.auto,
            )

        else:
            raise ValueError(
                f"Unknown interrupt payload: {payload}"
            )

        result = app.invoke(
            Command(resume=decision),
            run_config,
            context=context,
        )

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
