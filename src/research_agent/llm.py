"""Single place the LLM is constructed — swap the model via RESEARCH_AGENT_MODEL."""

from langchain_anthropic import ChatAnthropic

from . import config


def get_llm(max_tokens: int | None = None) -> ChatAnthropic:
    return ChatAnthropic(
        model=config.MODEL,
        max_tokens=max_tokens or config.MAX_TOKENS,
        timeout=180,
    )
