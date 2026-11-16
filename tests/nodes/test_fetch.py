

from research_agent import nodes

from unittest.mock import MagicMock

from threading import Barrier, Lock

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


def test_fetch_respects_max_concurrent_acquisitions(monkeypatch):
    monkeypatch.setattr(
        nodes.config,
        "MAX_CONCURRENT_ACQUISITIONS",
        2,
    )

    barrier = Barrier(2)
    lock = Lock()

    active = 0
    max_active = 0

    def fake_acquire(search_result, options=None):
        nonlocal active, max_active

        with lock:
            active += 1
            max_active = max(max_active, active)

        try:
            barrier.wait(timeout=3)
        finally:
            with lock:
                active -= 1

        return AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
        )

    monkeypatch.setattr(nodes, "acquire_resource", fake_acquire)

    results = [
        SearchResult(title=f"Article {i}", url=f"https://site{i}.com")
        for i in range(4)
    ]

    out = nodes.fetch({"search_results": results})

    assert len(out["acquired_resources"]) == 4
    assert max_active == 2

def test_fetch_deduplicates_same_url_within_round(monkeypatch):
    calls = []

    def fake_acquire(search_result, options=None):
        calls.append(search_result.url)
        return AcquisitionResult(status=AcquisitionStatus.SUCCESS)

    monkeypatch.setattr(nodes, "acquire_resource", fake_acquire)

    url = "https://example.com/article"

    results = [
        SearchResult(title="Article", url=url),
        SearchResult(title="Duplicate", url=url),
    ]

    out = nodes.fetch({"search_results": results})

    assert calls == [url]
    assert len(out["acquired_resources"]) == 1

def test_fetch_does_not_retry_after_attempt_limit(monkeypatch):
    monkeypatch.setattr(
        nodes.config,
        "MAX_ACQUISITION_ATTEMPTS",
        2,
    )

    search_result = SearchResult(
        title="Failed article",
        url="https://example.com/article",
    )

    previous_resource = AcquiredResource(
        search_result=search_result,
        acquisition=AcquisitionResult(
            status=AcquisitionStatus.FAILED,
            error=AcquisitionError(
                code="DOWNLOAD_FAILED",
                message="Download failed",
            ),
        ),
        attempt_count=2,
    )

    calls = []

    def fake_acquire(search_result, options=None):
        calls.append(search_result.url)
        return AcquisitionResult(status=AcquisitionStatus.SUCCESS)

    monkeypatch.setattr(nodes, "acquire_resource", fake_acquire)

    out = nodes.fetch({
        "search_results": [search_result],
        "acquired_resources": [previous_resource],
    })

    assert calls == []
    assert out["acquired_resources"][0] is previous_resource

def test_fetch_schedules_existing_resource_only_once(monkeypatch):
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/article"

    previous_result = SearchResult(
        title="Original",
        url=original_url,
    )

    previous_resource = AcquiredResource(
        search_result=previous_result,
        acquisition=AcquisitionResult(
            status=AcquisitionStatus.FAILED,
            original_url=original_url,
            final_url=final_url,
            error=AcquisitionError(
                code="DOWNLOAD_FAILED",
                message="Download failed",
            ),
        ),
        attempt_count=1,
    )

    calls = []

    def fake_acquire(search_result, options=None):
        calls.append(search_result.url)
        return AcquisitionResult(status=AcquisitionStatus.SUCCESS)

    monkeypatch.setattr(nodes, "acquire_resource", fake_acquire)

    monkeypatch.setattr(
        nodes.config,
        "MAX_ACQUISITION_ATTEMPTS",
        2,
    )

    results = [
        SearchResult(title="Original", url=original_url),
        SearchResult(title="Final", url=final_url),
    ]

    out = nodes.fetch({
        "search_results": results,
        "acquired_resources": [previous_resource],
    })

    assert len(calls) == 1
    assert len(out["acquired_resources"]) == 1
    assert out["acquired_resources"][0].attempt_count == 2

def test_fetch_preserves_input_order(monkeypatch):
    import time

    completion_order = []

    delays = {
        "https://a.com": 0.3,
        "https://b.com": 0.2,
        "https://c.com": 0.1,
    }

    def fake_acquire(search_result, options=None):
        time.sleep(delays[search_result.url])
        completion_order.append(search_result.url)

        return AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
        )

    monkeypatch.setattr(
        nodes,
        "acquire_resource",
        fake_acquire,
    )

    results = [
        SearchResult(title="A", url="https://a.com"),
        SearchResult(title="B", url="https://b.com"),
        SearchResult(title="C", url="https://c.com"),
    ]

    out = nodes.fetch({"search_results": results})

    output_order = [
        item.search_result.url
        for item in out["acquired_resources"]
    ]

    assert completion_order != output_order

    assert output_order == [
        "https://a.com",
        "https://b.com",
        "https://c.com",
    ]


