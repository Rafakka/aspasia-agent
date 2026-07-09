"""Runtime configuration, overridable via environment variables (see .env.example)."""

import os

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("RESEARCH_AGENT_MODEL", "claude-opus-4-8")
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "8"))
MAX_SOURCES = int(os.getenv("MAX_SOURCES", "6"))
MIN_SOURCES = int(os.getenv("MIN_SOURCES", "3"))
MAX_SEARCH_ROUNDS = int(os.getenv("MAX_SEARCH_ROUNDS", "2"))
MAX_PAGE_CHARS = int(os.getenv("MAX_PAGE_CHARS", "8000"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8192"))
FETCH_TIMEOUT_S = float(os.getenv("FETCH_TIMEOUT_S", "15"))
