
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from research_agent.core.models.resource import ResourceType


def detect_resource_type(
    content: bytes,
    content_type: str | None = None,
    url: str | None = None,
) -> ResourceType:
    """
    Detects the logical type of a digital resource.

    Detection priority:
        1. Binary signatures (magic bytes).
        2. HTTP Content-Type.
        3. URL extension.
        4. ResourceType.OTHER.

    The detector does not download, store, or extract resources.
    """

    if not content:
        return ResourceType.OTHER

    detected = _detect_by_signature(content)

    if detected is not None:
        return detected

    detected = _detect_by_mime_type(content_type)

    if detected is not None:
        return detected

    detected = _detect_by_url(url)

    if detected is not None:
        return detected

    return ResourceType.OTHER


def _detect_by_signature(content: bytes) -> ResourceType | None:
    """
    Identifies resource types using their binary signatures.
    """

    # PDF
    if content.startswith(b"%PDF-"):
        return ResourceType.PDF

    # PNG
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ResourceType.IMAGE

    # JPEG
    if content.startswith(b"\xff\xd8\xff"):
        return ResourceType.IMAGE

    # GIF
    if content.startswith((b"GIF87a", b"GIF89a")):
        return ResourceType.IMAGE

    # WebP
    if (
        len(content) >= 12
        and content.startswith(b"RIFF")
        and content[8:12] == b"WEBP"
    ):
        return ResourceType.IMAGE

    # ZIP-based formats, including XLSX.
    if content.startswith(b"PK\x03\x04"):
        return _detect_zip_resource(content)

    # HTML signatures, allowing leading whitespace and BOM.
    if _looks_like_html(content):
        return ResourceType.HTML

    return None


def _detect_zip_resource(content: bytes) -> ResourceType:
    """
    Distinguishes XLSX files from generic ZIP archives.
    """

    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())

            if (
                "[Content_Types].xml" in names
                and "xl/workbook.xml" in names
            ):
                return ResourceType.SPREADSHEET

    except (BadZipFile, OSError):
        pass

    return ResourceType.OTHER


def _looks_like_html(content: bytes) -> bool:
    """
    Checks whether the beginning of the content resembles HTML.
    """

    prefix = content[:4096]

    # Remove UTF-8 BOM and leading whitespace.
    prefix = prefix.removeprefix(b"\xef\xbb\xbf").lstrip()

    prefix = prefix.lower()

    html_markers = (
        b"<!doctype html",
        b"<html",
        b"<head",
        b"<body",
    )

    return prefix.startswith(html_markers)


def _detect_by_mime_type(
    content_type: str | None,
) -> ResourceType | None:
    """
    Identifies resource types using the HTTP Content-Type header.
    """

    if not content_type:
        return None

    mime_type = content_type.split(";")[0].strip().lower()

    if mime_type in {
        "application/pdf",
    }:
        return ResourceType.PDF

    if mime_type in {
        "text/html",
        "application/xhtml+xml",
    }:
        return ResourceType.HTML

    if mime_type in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "application/csv",
    }:
        return ResourceType.SPREADSHEET

    if mime_type.startswith("image/"):
        return ResourceType.IMAGE

    return None


def _detect_by_url(url: str | None) -> ResourceType | None:
    """
    Uses the URL extension as a fallback classification mechanism.
    """

    if not url:
        return None

    from urllib.parse import urlparse

    path = urlparse(url).path.lower()

    if path.endswith(".pdf"):
        return ResourceType.PDF

    if path.endswith((".html", ".htm", ".xhtml")):
        return ResourceType.HTML

    if path.endswith((".xlsx", ".xls", ".csv")):
        return ResourceType.SPREADSHEET

    if path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        return ResourceType.IMAGE

    return None

