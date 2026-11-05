


import hashlib
import os

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from research_agent.core.models.resource import Resource, ResourceType


DEFAULT_STORAGE_DIR = Path("data/resources")

# Whitelist of extensions. We never use arbitrary URL filenames.
RESOURCE_EXTENSIONS = {
    ResourceType.HTML: ".html",
    ResourceType.PDF: ".pdf",
    ResourceType.SPREADSHEET: ".xlsx",
    ResourceType.IMAGE: ".img",
    ResourceType.OTHER: ".bin",
}


def get_storage_root() -> Path:
    """
    Returns the root directory used by Aspásia to store resources.

    ASPASIA_STORAGE_DIR can override the default directory.
    """

    configured_path = os.getenv("ASPASIA_STORAGE_DIR")

    if configured_path:
        return Path(configured_path).expanduser().resolve()

    return DEFAULT_STORAGE_DIR.resolve()


def calculate_sha256(content: bytes) -> str:
    """
    Calculates the SHA-256 hash of the original resource.
    """

    return hashlib.sha256(content).hexdigest()


def get_file_extension(resource: Resource) -> str:
    """
    Determines a safe file extension based on resource metadata.

    The MIME type is preferred when it distinguishes formats
    that share the same logical ResourceType.
    """

    mime_type = (resource.mime_type or "").split(";")[0].strip().lower()

    mime_extensions = {
        "text/html": ".html",
        "application/xhtml+xml": ".xhtml",
        "application/pdf": ".pdf",
        "text/csv": ".csv",
        "application/csv": ".csv",
        "application/vnd.ms-excel": ".xls",
        (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ): ".xlsx",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }

    if mime_type in mime_extensions:
        return mime_extensions[mime_type]

    return RESOURCE_EXTENSIONS.get(
        resource.resource_type,
        ".bin",
    )


def store_resource(
    resource: Resource,
    content: bytes,
) -> Resource:
    """
    Stores the original resource in Aspásia's local storage.

    Returns an updated Resource containing:
        - content_hash
        - storage_path
        - acquired_at

    The storage_path is relative to the configured storage root.

    Raises:
        ValueError: If the resource content is empty.
        OSError: If the filesystem operation fails.
    """

    if not content:
        raise ValueError("Cannot store an empty resource.")

    storage_root = get_storage_root()

    # Use the acquisition date to organize resources.
    acquired_at = datetime.now(timezone.utc)

    date_directory = Path(
        str(acquired_at.year),
        f"{acquired_at.month:02d}",
        f"{acquired_at.day:02d}",
    )

    extension = get_file_extension(resource)

    filename = f"{resource.id}{extension}"

    relative_path = date_directory / filename
    absolute_path = storage_root / relative_path

    # Ensure the destination directory exists.
    absolute_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Calculate the hash before writing.
    content_hash = calculate_sha256(content)

    # Write to a temporary file before replacing the destination.
    temporary_path = absolute_path.with_name(
        f"{absolute_path.name}.tmp"
    )

    try:
        temporary_path.write_bytes(content)
        os.replace(temporary_path, absolute_path)

    except OSError:
        # Clean up a temporary file if writing or replacement fails.
        temporary_path.unlink(missing_ok=True)
        raise

    # Return a new Resource instance with storage metadata.
    return resource.model_copy(
        update={
            "content_hash": content_hash,
            "storage_path": relative_path.as_posix(),
            "acquired_at": acquired_at,
        }
    )

