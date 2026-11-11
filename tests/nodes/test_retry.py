
import pytest

from research_agent import config, nodes
from research_agent.state import SearchResult

from research_agent.nodes import should_retry_acquisition

from research_agent.ingestion.acquisition import (
    AcquisitionResult,
    AcquisitionStatus,
    AcquisitionError,
)
from research_agent.state import AcquiredResource



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

