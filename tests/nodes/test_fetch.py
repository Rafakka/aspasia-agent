

from research_agent import nodes

from unittest.mock import MagicMock

from research_agent.state import SearchResult

from research_agent.ingestion.acquisition import (
    AcquisitionResult,
    AcquisitionStatus,
    AcquisitionError,
)
from research_agent.state import AcquiredResource

from research_agent.ingestion.acquisition import _build_acquisition_result

from research_agent.core.models.resource import Resource, ResourceType

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


def test_fetch_retries_resource_discovered_by_final_url(
    monkeypatch,
):
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/article"

    search_result = SearchResult(
        title="Article",
        url=original_url,
    )

    failed_acquisition = AcquisitionResult(
        status=AcquisitionStatus.FAILED,
        original_url=original_url,
        final_url=final_url,
        error=AcquisitionError(
            code="EXTRACTION_FAILED",
            message="Could not extract content",
        ),
    )

    previous_resource = AcquiredResource(
        search_result=search_result,
        acquisition=failed_acquisition,
        attempt_count=1,
    )

    new_search_result = SearchResult(
        title="Article rediscovered",
        url=final_url,
    )

    successful_acquisition = AcquisitionResult(
        status=AcquisitionStatus.SUCCESS,
    )

    calls = []

    def fake_acquire_resource(search_result, options):
        calls.append(search_result.url)
        return successful_acquisition

    monkeypatch.setattr(
        nodes,
        "acquire_resource",
        fake_acquire_resource,
    )

    monkeypatch.setattr(
        nodes.config,
        "MAX_ACQUISITION_ATTEMPTS",
        2,
    )

    result = nodes.fetch({
        "search_results": [new_search_result],
        "acquired_resources": [previous_resource],
    })

    assert calls == [final_url]
    assert len(result["acquired_resources"]) == 1

    updated_resource = result["acquired_resources"][0]

    assert updated_resource.attempt_count == 2
    assert updated_resource.search_result.url == final_url
    assert updated_resource.acquisition is successful_acquisition


def test_fetch_matches_final_url_without_resource(
    monkeypatch,
):
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/article"

    previous_search_result = SearchResult(
        title="Original article",
        url=original_url,
    )

    failed_acquisition = AcquisitionResult(
        status=AcquisitionStatus.FAILED,
        original_url=original_url,
        final_url=final_url,
        error=AcquisitionError(
            code="DOWNLOAD_FAILED",
            message="Download failed after redirect",
        ),
    )

    previous_resource = AcquiredResource(
        search_result=previous_search_result,
        acquisition=failed_acquisition,
        attempt_count=1,
    )

    new_search_result = SearchResult(
        title="Rediscovered article",
        url=final_url,
    )

    successful_acquisition = AcquisitionResult(
        status=AcquisitionStatus.SUCCESS,
    )

    calls = []

    def fake_acquire_resource(search_result, options):
        calls.append(search_result.url)
        return successful_acquisition

    monkeypatch.setattr(
        nodes,
        "acquire_resource",
        fake_acquire_resource,
    )

    monkeypatch.setattr(
        nodes.config,
        "MAX_ACQUISITION_ATTEMPTS",
        2,
    )

    result = nodes.fetch({
        "search_results": [new_search_result],
        "acquired_resources": [previous_resource],
    })

    assert calls == [final_url]
    assert len(result["acquired_resources"]) == 1

    updated_resource = result["acquired_resources"][0]

    assert updated_resource.attempt_count == 2
    assert updated_resource.acquisition is successful_acquisition


def test_build_acquisition_result_preserves_urls():
    result = _build_acquisition_result(
        status=AcquisitionStatus.FAILED,
        original_url="https://example.com/redirect",
        final_url="https://example.com/article",
    )

    assert result.original_url == "https://example.com/redirect"
    assert result.final_url == "https://example.com/article"


def test_build_acquisition_result_uses_resource_url_as_fallback():
    resource = Resource(
        url="https://example.com/article",
        resource_type=ResourceType.HTML,
    )

    result = _build_acquisition_result(
        status=AcquisitionStatus.PARTIAL,
        original_url="https://example.com/redirect",
        resource=resource,
    )

    assert result.original_url == "https://example.com/redirect"
    assert result.final_url == resource.url
    assert result.resource is resource

