
from unittest.mock import patch

from research_agent.state import SearchResult
from research_agent.core.models.resource import ResourceType
from research_agent.ingestion.acquisition import (
    acquire_resource,
    AcquisitionOptions,
    AcquisitionStatus,
)


def test_pdf_is_stored_without_extraction():

    search_result = SearchResult(
        title="Example PDF",
        url="https://example.com/document.pdf",
    )

    fake_response = type(
        "Response",
        (),
        {
            "content": b"%PDF-1.7 fake pdf content",
            "url": "https://example.com/document.pdf",
            "headers": {
                "content-type": "application/pdf"
            },
            "raise_for_status": lambda self: None,
        },
    )()

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
    assert result.resource is not None
    assert result.resource.resource_type == ResourceType.PDF
    assert result.resource.storage_path == "2026/11/05/example.pdf"
    assert result.extracted_content is None

