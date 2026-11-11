
import httpx

from unittest.mock import patch

from research_agent.discovery.models import SearchResult
from research_agent.core.models.resource import ResourceType
from research_agent.ingestion.acquisition import (
    acquire_resource,
    AcquisitionOptions,
    AcquisitionStatus,
)


def test_pdf_is_stored_without_extraction():
    original_url = "https://example.com/document.pdf"

    search_result = SearchResult(
        title="Example PDF",
        url=original_url,
    )

    fake_response = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", original_url),
        headers={
            "content-type": "application/pdf",
        },
        content=b"%PDF-1.7 fake pdf content",
    )

    with (
        patch(
            "research_agent.ingestion.acquisition.httpx.get",
            return_value=fake_response,
        ),
        patch(
            "research_agent.ingestion.acquisition.store_resource",
            side_effect=lambda resource, content: resource.model_copy(
                update={
                    "storage_path": "2026/11/05/example.pdf",
                    "content_hash": "fakehash",
                }
            ),
        ),
    ):
        result = acquire_resource(
            search_result,
            AcquisitionOptions(
                store_original=True,
                extract_content=True,
            ),
        )

    assert result.status == AcquisitionStatus.UNSUPPORTED_EXTRACTION
    assert result.original_url == original_url
    assert result.final_url == original_url

    assert result.resource is not None
    assert result.resource.resource_type == ResourceType.PDF
    assert result.resource.storage_path == "2026/11/05/example.pdf"

    assert result.extracted_content is None

