"""Node-level tests: every node is exercised in isolation with stubbed LLM/network calls."""

import pytest

from research_agent import config, nodes
from research_agent.state import ResearchPlan, SearchResult, SourceSelection

from research_agent.nodes import should_retry_acquisition

from research_agent.ingestion.acquisition import (
    AcquisitionResult,
    AcquisitionStatus,
    AcquisitionError,
)
from research_agent.state import AcquiredResource

class StubLLM:
    """Stands in for ChatAnthropic: records prompts, returns canned results."""

    def __init__(self, result):
        self.result = result
        self.prompts = []

    def with_structured_output(self, schema):
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.result


PLAN = ResearchPlan(
    objective="Explain X",
    search_queries=["x basics", "x criticism"],
    outline=["Background", "Findings"],
).model_dump()


def test_plan_node_returns_plan_and_clears_feedback(monkeypatch):
    stub = StubLLM(ResearchPlan.model_validate(PLAN))
    monkeypatch.setattr(nodes.llm, "get_llm", lambda **kw: stub)
    out = nodes.plan({"topic": "X", "feedback": "too narrow"})
    assert out["plan"] == PLAN
    assert out["feedback"] == ""
    # human feedback must actually reach the prompt on a revision pass
    assert "too narrow" in stub.prompts[0]


def test_search_broadens_queries_on_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(nodes.search_tool, "web_search", lambda q, **kw: calls.append(q) or [])
    nodes.search({"topic": "X", "plan": PLAN, "search_round": 1})
    assert "X overview" in calls  # round 2 adds broadened queries
    assert "x basics" in calls


def test_select_sources_drops_hallucinated_urls(monkeypatch):
    candidates = [SearchResult(title="A", url="https://a.com"), SearchResult(title="B", url="https://b.com")]
    selection = SourceSelection(urls=["https://a.com", "https://fake.invalid"], reasoning="test")
    monkeypatch.setattr(nodes.llm, "get_llm", lambda **kw: StubLLM(selection))
    out = nodes.select_sources({"plan": PLAN, "search_results": candidates})
    assert [r.url for r in out["search_results"]] == ["https://a.com"]


def test_fetch_accumulates_acquired_resources(monkeypatch):
    calls = []

    def fake_acquire(search_result, options=None):
        calls.append(search_result.url)

        assert options.store_original is True
        assert options.extract_content is True

        return AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
        )

    monkeypatch.setattr(nodes, "acquire_resource", fake_acquire)

    previous_result = SearchResult(
        title="Previous",
        url="https://previous.com",
    )

    previous_resource = AcquiredResource(
        search_result=previous_result,
        acquisition=AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
        ),
    )

    new_results = [
        SearchResult(title="A", url="https://a.com"),
        SearchResult(title="B", url="https://b.com"),
    ]

    out = nodes.fetch(
        {
            "search_results": new_results,
            "acquired_resources": [previous_resource],
        }
    )

    assert len(calls) == 2

    assert len(out["acquired_resources"]) == 3

    # Previous results must be preserved.
    assert out["acquired_resources"][0] is previous_resource

    # New results must be appended.
    assert out["acquired_resources"][1].search_result.url == "https://a.com"
    assert out["acquired_resources"][2].search_result.url == "https://b.com"

def test_fetch_continues_after_unexpected_acquisition_error(monkeypatch):
    def fake_acquire(search_result, options=None):
        if "bad" in search_result.url:
            raise RuntimeError("Unexpected failure")

        return AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
        )

    monkeypatch.setattr(nodes, "acquire_resource", fake_acquire)

    results = [
        SearchResult(title="Bad", url="https://bad.com"),
        SearchResult(title="Good", url="https://good.com"),
    ]

    out = nodes.fetch({"search_results": results})

    acquired = out["acquired_resources"]

    assert len(acquired) == 2

    assert acquired[0].acquisition.status == AcquisitionStatus.FAILED

    assert acquired[1].acquisition.status == AcquisitionStatus.SUCCESS


def test_route_after_fetch_counts_extracted_content(monkeypatch):
    monkeypatch.setattr(config, "MIN_SOURCES", 2)

    results = [
        AcquiredResource(
            search_result=SearchResult(
                title="HTML A",
                url="https://a.com",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Useful extracted content",
            ),
        ),
        AcquiredResource(
            search_result=SearchResult(
                title="PDF",
                url="https://b.com/file.pdf",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.UNSUPPORTED_EXTRACTION,
            ),
        ),
        AcquiredResource(
            search_result=SearchResult(
                title="HTML C",
                url="https://c.com",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="   ",
            ),
        ),
    ]

    result = nodes.route_after_fetch(
        {
            "acquired_resources": results,
            "search_round": 1,
        }
    )

    assert result == "search"


def test_route_after_fetch_synthesizes_with_enough_content(monkeypatch):
    monkeypatch.setattr(config, "MIN_SOURCES", 2)

    results = [
        AcquiredResource(
            search_result=SearchResult(title="A", url="https://a.com"),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Content A",
            ),
        ),
        AcquiredResource(
            search_result=SearchResult(title="B", url="https://b.com"),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.PARTIAL,
                extracted_content="Content B",
            ),
        ),
    ]

    result = nodes.route_after_fetch(
        {
            "acquired_resources": results,
            "search_round": 1,
        }
    )

    assert result == "synthesize"


def test_route_after_fetch_respects_max_search_rounds(monkeypatch):
    monkeypatch.setattr(config, "MIN_SOURCES", 3)
    monkeypatch.setattr(config, "MAX_SEARCH_ROUNDS", 2)

    result = nodes.route_after_fetch(
        {
            "acquired_resources": [],
            "search_round": 2,
        }
    )

    assert result == "synthesize"


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



@pytest.mark.parametrize(
    "n_sources,search_round,expected",
    [
        (config.MIN_SOURCES, 1, "synthesize"),
        (0, 1, "search"),
        (0, config.MAX_SEARCH_ROUNDS, "synthesize"),
    ],
)
def test_route_after_fetch(n_sources, search_round, expected):
    acquired_resources = [
        AcquiredResource(
            search_result=SearchResult(
                title=f"Source {i}",
                url=f"https://source{i}.com",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Useful extracted content",
            ),
        )
        for i in range(n_sources)
    ]

    state = {
        "acquired_resources": acquired_resources,
        "search_round": search_round,
    }

    assert nodes.route_after_fetch(state) == expected

@pytest.mark.parametrize(
    ("status", "error_code", "expected"),
    [
        # Successful acquisition: no retry
        (AcquisitionStatus.SUCCESS, None, False),

        # Retryable failures
        (AcquisitionStatus.FAILED, "DOWNLOAD_FAILED", True),
        (AcquisitionStatus.FAILED, "EMPTY_RESOURCE", True),
        (AcquisitionStatus.PARTIAL, "EXTRACTION_FAILED", True),
        (
            AcquisitionStatus.FAILED,
            "UNEXPECTED_ACQUISITION_ERROR",
            True,
        ),

        # Non-retryable failures
        (AcquisitionStatus.FAILED, "STORAGE_FAILED", False),
        (
            AcquisitionStatus.FAILED,
            "RESOURCE_DETECTION_FAILED",
            False,
        ),
        (AcquisitionStatus.PARTIAL, "EMPTY_EXTRACTION", False),
        (
            AcquisitionStatus.UNSUPPORTED_EXTRACTION,
            "PDF_EXTRACTION_UNSUPPORTED",
            False,
        ),
        (
            AcquisitionStatus.UNSUPPORTED_EXTRACTION,
            "UNSUPPORTED_RESOURCE_TYPE",
            False,
        ),
        (AcquisitionStatus.FAILED, "INVALID_OPTIONS", False),
    ],
)
def test_should_retry_acquisition(
    status,
    error_code,
    expected,
):
    acquisition = AcquisitionResult(
        status=status,
        error=(
            AcquisitionError(
                code=error_code,
                message="Test error",
            )
            if error_code
            else None
        ),
    )

    assert should_retry_acquisition(acquisition) is expected

def test_should_not_retry_acquisition_with_extracted_content():
    acquisition = AcquisitionResult(
        status=AcquisitionStatus.PARTIAL,
        extracted_content="Some extracted content",
        error=AcquisitionError(
            code="EXTRACTION_FAILED",
            message="Partial extraction",
        ),
    )

    assert should_retry_acquisition(acquisition) is False

def test_acquired_resource_defaults_to_one_attempt():
    resource = AcquiredResource(
        search_result=SearchResult(
            title="Example",
            url="https://example.com",
        ),
        acquisition=AcquisitionResult(
            status=AcquisitionStatus.FAILED,
            error=AcquisitionError(
                code="DOWNLOAD_FAILED",
                message="Connection timeout",
            ),
        ),
    )

    assert resource.attempt_count == 1

def test_acquired_resource_accepts_attempt_count():
    resource = AcquiredResource(
        search_result=SearchResult(
            title="Example",
            url="https://example.com",
        ),
        acquisition=AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
        ),
        attempt_count=2,
    )

    assert resource.attempt_count == 2

def test_fetch_skips_previously_successful_source(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Source should not be acquired again")

    monkeypatch.setattr(nodes, "acquire_resource", fail_if_called)

    previous = AcquiredResource(
        search_result=SearchResult(
            title="Source A",
            url="https://example.com/",
        ),
        acquisition=AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
            extracted_content="Existing content",
        ),
    )

    out = nodes.fetch({
        "search_results": [
            SearchResult(
                title="Source A",
                url="https://EXAMPLE.com",
            )
        ],
        "acquired_resources": [previous],
    })

    assert len(out["acquired_resources"]) == 1
    assert out["acquired_resources"][0].attempt_count == 1

def test_fetch_retries_retryable_source(monkeypatch):
    calls = []

    def fake_acquire(search_result, options=None):
        calls.append(search_result.url)

        return AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
            extracted_content="Recovered content",
        )

    monkeypatch.setattr(nodes, "acquire_resource", fake_acquire)

    previous = AcquiredResource(
        search_result=SearchResult(
            title="Source A",
            url="https://example.com",
        ),
        acquisition=AcquisitionResult(
            status=AcquisitionStatus.FAILED,
            error=AcquisitionError(
                code="DOWNLOAD_FAILED",
                message="Connection timeout",
            ),
        ),
    )

    out = nodes.fetch({
        "search_results": [
            SearchResult(
                title="Source A",
                url="https://example.com/",
            )
        ],
        "acquired_resources": [previous],
    })

    acquired = out["acquired_resources"]

    assert len(calls) == 1
    assert len(acquired) == 1
    assert acquired[0].acquisition.status == AcquisitionStatus.SUCCESS
    assert acquired[0].attempt_count == 2

def test_fetch_skips_non_retryable_source(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Source should not be retried")

    monkeypatch.setattr(nodes, "acquire_resource", fail_if_called)

    previous = AcquiredResource(
        search_result=SearchResult(
            title="PDF Source",
            url="https://example.com/document.pdf",
        ),
        acquisition=AcquisitionResult(
            status=AcquisitionStatus.UNSUPPORTED_EXTRACTION,
            error=AcquisitionError(
                code="PDF_EXTRACTION_UNSUPPORTED",
                message="PDF extraction is not supported",
            ),
        ),
    )

    out = nodes.fetch({
        "search_results": [
            SearchResult(
                title="PDF Source",
                url="https://example.com/document.pdf",
            )
        ],
        "acquired_resources": [previous],
    })

    assert len(out["acquired_resources"]) == 1
    assert out["acquired_resources"][0].attempt_count == 1

def test_fetch_does_not_retry_after_max_attempts(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Maximum attempts already reached")

    monkeypatch.setattr(nodes, "acquire_resource", fail_if_called)

    previous = AcquiredResource(
        search_result=SearchResult(
            title="Source A",
            url="https://example.com",
        ),
        acquisition=AcquisitionResult(
            status=AcquisitionStatus.FAILED,
            error=AcquisitionError(
                code="DOWNLOAD_FAILED",
                message="Connection timeout",
            ),
        ),
        attempt_count=2,
    )

    out = nodes.fetch({
        "search_results": [
            SearchResult(
                title="Source A",
                url="https://example.com/",
            )
        ],
        "acquired_resources": [previous],
    })

    assert len(out["acquired_resources"]) == 1
    assert out["acquired_resources"][0].attempt_count == 2


def test_route_after_fetch_counts_unique_sources(monkeypatch):
    monkeypatch.setattr(config, "MIN_SOURCES", 2)
    monkeypatch.setattr(config, "MAX_SEARCH_ROUNDS", 2)

    resources = [
        AcquiredResource(
            search_result=SearchResult(
                title="Source A",
                url="https://example.com/article/",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Content A",
            ),
        ),
        AcquiredResource(
            search_result=SearchResult(
                title="Source A duplicate",
                url="https://EXAMPLE.com/article",
            ),
            acquisition=AcquisitionResult(
                status=AcquisitionStatus.SUCCESS,
                extracted_content="Content A duplicate",
            ),
        ),
    ]

    result = nodes.route_after_fetch({
        "acquired_resources": resources,
        "search_round": 1,
    })

    assert result == "search"

def test_fetch_and_route_across_two_search_rounds(monkeypatch):
    monkeypatch.setattr(config, "MIN_SOURCES", 1)
    monkeypatch.setattr(config, "MAX_SEARCH_ROUNDS", 2)

    calls = []

    def fake_acquire(search_result, options=None):
        calls.append(search_result.url)

        if len(calls) == 1:
            return AcquisitionResult(
                status=AcquisitionStatus.FAILED,
                error=AcquisitionError(
                    code="DOWNLOAD_FAILED",
                    message="Connection timeout",
                ),
            )

        return AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
            extracted_content="Recovered research content",
        )

    monkeypatch.setattr(nodes, "acquire_resource", fake_acquire)

    # First search round
    first_result = SearchResult(
        title="Source A",
        url="https://example.com/article/",
    )

    first_fetch = nodes.fetch({
        "search_results": [first_result],
    })

    first_resources = first_fetch["acquired_resources"]

    assert len(first_resources) == 1
    assert first_resources[0].attempt_count == 1

    first_route = nodes.route_after_fetch({
        "acquired_resources": first_resources,
        "search_round": 1,
    })

    assert first_route == "search"

    # Second search round: equivalent URL
    second_result = SearchResult(
        title="Source A",
        url="https://EXAMPLE.com/article",
    )

    second_fetch = nodes.fetch({
        "search_results": [second_result],
        "acquired_resources": first_resources,
    })

    second_resources = second_fetch["acquired_resources"]

    assert len(calls) == 2
    assert len(second_resources) == 1

    assert second_resources[0].attempt_count == 2
    assert (
        second_resources[0].acquisition.status
        == AcquisitionStatus.SUCCESS
    )
    assert (
        second_resources[0].acquisition.extracted_content
        == "Recovered research content"
    )

    second_route = nodes.route_after_fetch({
        "acquired_resources": second_resources,
        "search_round": 2,
    })

    assert second_route == "synthesize"
