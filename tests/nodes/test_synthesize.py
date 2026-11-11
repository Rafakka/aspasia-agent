
from research_agent import nodes
from research_agent.state import SearchResult

from research_agent.ingestion.acquisition import (
    AcquisitionResult,
    AcquisitionStatus,
)
from research_agent.state import AcquiredResource


def test_synthesize_without_resources(monkeypatch):
    def fail_if_called():
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(nodes.llm, "get_llm", fail_if_called)

    result = nodes.synthesize({"acquired_resources": []})

    assert result["report"] == (
        "zero recursos, favor consultar busca de fontes"
    )

def test_synthesize_uses_acquired_resources(monkeypatch):
    class FakeResponse:
        text = "# Research Report"
        usage_metadata = None

    class FakeLLM:
        def invoke(self, prompt):
            assert "Useful extracted content" in prompt
            assert "https://source.com" in prompt
            assert "Source A" in prompt
            return FakeResponse()

    monkeypatch.setattr(nodes.llm, "get_llm", lambda: FakeLLM())

    resource = AcquiredResource(
        search_result=SearchResult(
            title="Source A",
            url="https://source.com",
        ),
        acquisition=AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
            extracted_content="Useful extracted content",
        ),
    )

    result = nodes.synthesize(
        {
            "topic": "Research topic",
            "plan": {
                "objective": "Understand the topic",
                "outline": ["Background"],
            },
            "acquired_resources": [resource],
        }
    )

    assert result["report"] == "# Research Report"
