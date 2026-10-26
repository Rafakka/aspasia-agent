"""Single place the LLM is constructed — swap the model via RESEARCH_AGENT_MODEL."""

from langchain_ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel

from . import config


def get_llm(max_tokens: int | None = None) -> BaseChatModel:
    return ChatOllama(
        model=config.MODEL,
        base_url="http://127.0.0.1:11434",
    )
