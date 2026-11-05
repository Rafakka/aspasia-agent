
import logging

from datetime import datetime, timezone
from enum import StrEnum

import httpx

from pydantic import BaseModel

from research_agent.core.models.resource import Resource, ResourceType
from research_agent.ingestion.detector import detect_resource_type
from research_agent.ingestion.storage import store_resource
from research_agent.ingestion.workers.html import extract_html
from research_agent.discovery.models import SearchResult


logger = logging.getLogger(__name__)


USER_AGENT = "Mozilla/5.0 (compatible; AspasiaResearchAgent/1.0)"
REQUEST_TIMEOUT = 30.0


class AcquisitionStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    UNSUPPORTED_EXTRACTION = "unsupported_extraction"


class AcquisitionOptions(BaseModel):
    """
    Controls the operations performed during acquisition.
    """

    store_original: bool = True
    extract_content: bool = True


class AcquisitionError(BaseModel):
    code: str
    message: str


class AcquisitionResult(BaseModel):
    """
    Represents the outcome of a resource acquisition operation.
    """

    status: AcquisitionStatus

    resource: Resource | None = None
    extracted_content: str | None = None
    error: AcquisitionError | None = None

    @property
    def succeeded(self) -> bool:
        return self.status in {
            AcquisitionStatus.SUCCESS,
            AcquisitionStatus.PARTIAL,
            AcquisitionStatus.UNSUPPORTED_EXTRACTION,
        }


def _failure(
    code: str,
    message: str,
    resource: Resource | None = None,
) -> AcquisitionResult:
    return AcquisitionResult(
        status=AcquisitionStatus.FAILED,
        resource=resource,
        error=AcquisitionError(
            code=code,
            message=message,
        ),
    )


def acquire_resource(
    search_result: SearchResult,
    options: AcquisitionOptions | None = None,
) -> AcquisitionResult:
    """
    Downloads, identifies, stores and optionally extracts a resource.

    HTML:
        Can be extracted with or without storing the original file.

    PDF:
        Can be downloaded and stored.
        Text extraction is not currently supported.

    Other formats:
        Can be stored, but extraction is not currently supported.
    """

    options = options or AcquisitionOptions()

    if not options.store_original and not options.extract_content:
        return _failure(
            code="INVALID_OPTIONS",
            message=(
                "At least one operation must be requested: "
                "store_original or extract_content."
            ),
        )

    # 1. Download resource.
    try:
        response = httpx.get(
            search_result.url,
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()

    except httpx.HTTPError as exc:
        logger.warning(
            "Resource download failed: %s",
            search_result.url,
            exc_info=True,
        )
        return _failure(
            code="DOWNLOAD_FAILED",
            message=str(exc),
        )

    content = response.content
    final_url = str(response.url)
    content_type = response.headers.get("content-type")

    if not content:
        return _failure(
            code="EMPTY_RESOURCE",
            message="The downloaded resource is empty.",
        )

    # 2. Detect resource type.
    try:
        resource_type = detect_resource_type(
            content=content,
            content_type=content_type,
            url=final_url,
        )

    except Exception as exc:
        logger.exception(
            "Resource detection failed: %s",
            final_url,
        )
        return _failure(
            code="RESOURCE_DETECTION_FAILED",
            message=str(exc),
        )

    # 3. Create resource metadata.
    resource = Resource(
        url=final_url,
        resource_type=resource_type,
        mime_type=content_type,
        acquired_at=datetime.now(timezone.utc),
    )

    # 4. Store original resource when requested.
    if options.store_original:
        try:
            resource = store_resource(
                resource=resource,
                content=content,
            )

        except (OSError, ValueError) as exc:
            logger.exception(
                "Resource storage failed: %s",
                final_url,
            )
            return _failure(
                code="STORAGE_FAILED",
                message=str(exc),
                resource=resource,
            )

    # 5. Return immediately if extraction was not requested.
    if not options.extract_content:
        return AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
            resource=resource,
        )

    # 6. PDF extraction is not implemented yet.
    if resource_type == ResourceType.PDF:
        if not options.store_original:
            return AcquisitionResult(
                status=AcquisitionStatus.UNSUPPORTED_EXTRACTION,
                resource=resource,
                error=AcquisitionError(
                    code="PDF_EXTRACTION_UNSUPPORTED",
                    message=(
                        "PDF extraction is not currently supported. "
                        "Enable store_original to preserve the PDF "
                        "and make it available to the user."
                    ),
                ),
            )

        return AcquisitionResult(
            status=AcquisitionStatus.UNSUPPORTED_EXTRACTION,
            resource=resource,
            error=AcquisitionError(
                code="PDF_EXTRACTION_UNSUPPORTED",
                message=(
                    "PDF extraction is not currently supported. "
                    f"The original file is available at: "
                    f"{resource.storage_path}"
                ),
            ),
        )

    # 7. Extract HTML content.
    if resource_type == ResourceType.HTML:
        try:
            extracted_content = extract_html(
                content=content,
                url=final_url,
            )

        except Exception as exc:
            logger.exception(
                "HTML extraction failed: %s",
                final_url,
            )
            return AcquisitionResult(
                status=AcquisitionStatus.PARTIAL,
                resource=resource,
                error=AcquisitionError(
                    code="EXTRACTION_FAILED",
                    message=str(exc),
                ),
            )

        if not extracted_content:
            return AcquisitionResult(
                status=AcquisitionStatus.PARTIAL,
                resource=resource,
                error=AcquisitionError(
                    code="EMPTY_EXTRACTION",
                    message=(
                        "The resource was acquired, but no "
                        "readable content could be extracted."
                    ),
                ),
            )

        return AcquisitionResult(
            status=AcquisitionStatus.SUCCESS,
            resource=resource,
            extracted_content=extracted_content,
        )

    # 8. Other resource types are not extractable yet.
    return AcquisitionResult(
        status=AcquisitionStatus.UNSUPPORTED_EXTRACTION,
        resource=resource,
        error=AcquisitionError(
            code="UNSUPPORTED_RESOURCE_TYPE",
            message=(
                "Content extraction is not currently supported "
                f"for resource type: {resource_type.value}."
            ),
        ),
    )

