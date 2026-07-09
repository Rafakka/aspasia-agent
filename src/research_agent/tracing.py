"""Run logging: every run writes a full trace to traces/ and a summary to the console."""

import logging
import sys
import time
from pathlib import Path


def setup_tracing(trace_dir: str = "traces") -> Path:
    """Configure logging; returns the path of this run's trace file."""
    Path(trace_dir).mkdir(exist_ok=True)
    trace_path = Path(trace_dir) / f"trace-{time.strftime('%Y%m%d-%H%M%S')}.log"

    root = logging.getLogger("research_agent")
    root.setLevel(logging.INFO)

    file_handler = logging.FileHandler(trace_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))

    root.handlers = [file_handler, console]
    return trace_path
