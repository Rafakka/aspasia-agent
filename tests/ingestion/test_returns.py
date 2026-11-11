
import httpx
import pytest

from research_agent.discovery.models import SearchResult
from research_agent.ingestion import acquisition

from research_agent.ingestion.acquisition import (
    AcquisitionOptions,
    AcquisitionStatus,
    ResourceType,
)


def make_search_result(
    url="https://example.com/redirect",
):
    return SearchResult(
        title="Test article",
        url=url,
    )


def make_response(
    url="https://example.com/article",
    content=b"<html><body>Article</body></html>",
    content_type="text/html",
    status_code=200,
):
    request = httpx.Request("GET", url)

    return httpx.Response(
        status_code=status_code,
        request=request,
        headers={"content-type": content_type},
        content=content,
    )


def mock_download(
    monkeypatch,
    response,
):
    monkeypatch.setattr(
        acquisition.httpx,
        "get",
        lambda *args, **kwargs: response,
    )


def mock_html_pipeline(monkeypatch):
    monkeypatch.setattr(
        acquisition,
        "detect_resource_type",
        lambda **kwargs: ResourceType.HTML,
    )

    monkeypatch.setattr(
        acquisition,
        "store_resource",
        lambda resource, content: resource,
    )

    monkeypatch.setattr(
        acquisition,
        "extract_html",
        lambda content, url: "Extracted article content",
    )


def assert_result_identity(
    result,
    original_url,
    final_url,
):
    assert result.original_url == original_url
    assert result.final_url == final_url


def assert_result_error(
    result,
    status,
    error_code,
):
    assert result.status == status
    assert result.error is not None
    assert result.error.code == error_code


def test_invalid_options_preserves_original_url():
    original_url = "https://example.com/redirect"

    result = acquisition.acquire_resource(
        search_result=make_search_result(original_url),
        options=AcquisitionOptions(
            store_original=False,
            extract_content=False,
        ),
    )

    assert_result_error(
        result,
        AcquisitionStatus.FAILED,
        "INVALID_OPTIONS",
    )

    assert result.original_url == original_url
    assert result.final_url is None
    assert result.resource is None


def test_download_failure_preserves_original_url(monkeypatch):
    original_url = "https://example.com/redirect"

    def fake_get(*args, **kwargs):
        request = httpx.Request("GET", original_url)
        raise httpx.ConnectError(
            "Connection failed",
            request=request,
        )

    monkeypatch.setattr(
        acquisition.httpx,
        "get",
        fake_get,
    )

    result = acquisition.acquire_resource(
        search_result=make_search_result(original_url),
    )

    assert_result_error(
        result,
        AcquisitionStatus.FAILED,
        "DOWNLOAD_FAILED",
    )

    assert result.original_url == original_url
    assert result.final_url is None
    assert result.resource is None


def test_http_error_after_redirect_preserves_final_url(monkeypatch):
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/article"

    response = make_response(
        url=final_url,
        content=b"Server error",
        status_code=500,
    )

    mock_download(monkeypatch, response)

    result = acquisition.acquire_resource(
        search_result=make_search_result(original_url),
    )

    assert_result_error(
        result,
        AcquisitionStatus.FAILED,
        "DOWNLOAD_FAILED",
    )

    assert_result_identity(
        result,
        original_url,
        final_url,
    )


def test_empty_resource_preserves_urls(monkeypatch):
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/article"

    response = make_response(
        url=final_url,
        content=b"",
    )

    mock_download(monkeypatch, response)

    result = acquisition.acquire_resource(
        search_result=make_search_result(original_url),
    )

    assert_result_error(
        result,
        AcquisitionStatus.FAILED,
        "EMPTY_RESOURCE",
    )

    assert_result_identity(
        result,
        original_url,
        final_url,
    )

    assert result.resource is None


def test_resource_detection_failure_preserves_urls(monkeypatch):
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/article"

    mock_download(
        monkeypatch,
        make_response(url=final_url),
    )

    def fake_detection(**kwargs):
        raise RuntimeError("Detection failed")

    monkeypatch.setattr(
        acquisition,
        "detect_resource_type",
        fake_detection,
    )

    result = acquisition.acquire_resource(
        search_result=make_search_result(original_url),
    )

    assert_result_error(
        result,
        AcquisitionStatus.FAILED,
        "RESOURCE_DETECTION_FAILED",
    )

    assert_result_identity(
        result,
        original_url,
        final_url,
    )

    assert result.resource is None


def test_storage_failure_preserves_resource_and_urls(monkeypatch):
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/article"

    mock_download(
        monkeypatch,
        make_response(url=final_url),
    )

    monkeypatch.setattr(
        acquisition,
        "detect_resource_type",
        lambda **kwargs: ResourceType.HTML,
    )

    def fake_storage(resource, content):
        raise OSError("Storage failed")

    monkeypatch.setattr(
        acquisition,
        "store_resource",
        fake_storage,
    )

    result = acquisition.acquire_resource(
        search_result=make_search_result(original_url),
    )

    assert_result_error(
        result,
        AcquisitionStatus.FAILED,
        "STORAGE_FAILED",
    )

    assert_result_identity(
        result,
        original_url,
        final_url,
    )

    assert result.resource is not None
    assert result.resource.url == final_url


def test_pdf_unsupported_extraction_preserves_urls(monkeypatch):
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/document.pdf"

    mock_download(
        monkeypatch,
        make_response(
            url=final_url,
            content=b"%PDF-1.4 test content",
            content_type="application/pdf",
        ),
    )

    monkeypatch.setattr(
        acquisition,
        "detect_resource_type",
        lambda **kwargs: ResourceType.PDF,
    )

    monkeypatch.setattr(
        acquisition,
        "store_resource",
        lambda resource, content: resource,
    )

    result = acquisition.acquire_resource(
        search_result=make_search_result(original_url),
    )

    assert_result_error(
        result,
        AcquisitionStatus.UNSUPPORTED_EXTRACTION,
        "PDF_EXTRACTION_UNSUPPORTED",
    )

    assert_result_identity(
        result,
        original_url,
        final_url,
    )

    assert result.resource is not None
    assert result.resource.url == final_url

def test_pdf_without_storage_preserves_urls(monkeypatch):
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/document.pdf"

    mock_download(
        monkeypatch,
        make_response(
            url=final_url,
            content=b"%PDF-1.4 test content",
            content_type="application/pdf",
        ),
    )

    monkeypatch.setattr(
        acquisition,
        "detect_resource_type",
        lambda **kwargs: ResourceType.PDF,
    )

    result = acquisition.acquire_resource(
        search_result=make_search_result(original_url),
        options=AcquisitionOptions(
            store_original=False,
            extract_content=True,
        ),
    )

    assert_result_error(
        result,
        AcquisitionStatus.UNSUPPORTED_EXTRACTION,
        "PDF_EXTRACTION_UNSUPPORTED",
    )

    assert_result_identity(
        result,
        original_url,
        final_url,
    )

    assert result.resource is not None


def test_html_extraction_failure_preserves_urls(monkeypatch):
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/article"

    mock_download(
        monkeypatch,
        make_response(url=final_url),
    )

    monkeypatch.setattr(
        acquisition,
        "detect_resource_type",
        lambda **kwargs: ResourceType.HTML,
    )

    monkeypatch.setattr(
        acquisition,
        "store_resource",
        lambda resource, content: resource,
    )

    def fake_extraction(content, url):
        raise RuntimeError("Extraction failed")

    monkeypatch.setattr(
        acquisition,
        "extract_html",
        fake_extraction,
    )

    result = acquisition.acquire_resource(
        search_result=make_search_result(original_url),
    )

    assert_result_error(
        result,
        AcquisitionStatus.PARTIAL,
        "EXTRACTION_FAILED",
    )

    assert_result_identity(
        result,
        original_url,
        final_url,
    )

    assert result.resource is not None
    assert result.resource.url == final_url


def test_empty_extraction_preserves_urls(monkeypatch):
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/article"

    mock_download(
        monkeypatch,
        make_response(url=final_url),
    )

    mock_html_pipeline(monkeypatch)

    monkeypatch.setattr(
        acquisition,
        "extract_html",
        lambda content, url: "",
    )

    result = acquisition.acquire_resource(
        search_result=make_search_result(original_url),
    )

    assert_result_error(
        result,
        AcquisitionStatus.PARTIAL,
        "EMPTY_EXTRACTION",
    )

    assert_result_identity(
        result,
        original_url,
        final_url,
    )

    assert result.resource is not None


def test_unsupported_resource_type_preserves_urls(monkeypatch):
    unsupported_type = next(
        (
            resource_type
            for resource_type in ResourceType
            if resource_type not in {
                ResourceType.HTML,
                ResourceType.PDF,
            }
        ),
        None,
    )

    if unsupported_type is None:
        pytest.skip("No additional ResourceType available")

    original_url = "https://example.com/redirect"
    final_url = "https://example.com/image"

    mock_download(
        monkeypatch,
        make_response(
            url=final_url,
            content=b"binary content",
            content_type="application/octet-stream",
        ),
    )

    monkeypatch.setattr(
        acquisition,
        "detect_resource_type",
        lambda **kwargs: unsupported_type,
    )

    monkeypatch.setattr(
        acquisition,
        "store_resource",
        lambda resource, content: resource,
    )

    result = acquisition.acquire_resource(
        search_result=make_search_result(original_url),
    )

    assert_result_error(
        result,
        AcquisitionStatus.UNSUPPORTED_EXTRACTION,
        "UNSUPPORTED_RESOURCE_TYPE",
    )

    assert_result_identity(
        result,
        original_url,
        final_url,
    )

    assert result.resource is not None



