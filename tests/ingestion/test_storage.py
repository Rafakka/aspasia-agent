

from pathlib import Path

import pytest

from research_agent.core.models.resource import Resource, ResourceType
from research_agent.ingestion.storage import (
    calculate_sha256,
    store_resource,
)

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from research_agent.ingestion import storage


def create_resource() -> Resource:
    return Resource(
        url="https://example.com/article",
        resource_type=ResourceType.HTML,
        mime_type="text/html",
    )


def test_store_resource_creates_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ASPASIA_STORAGE_DIR", str(tmp_path))

    resource = create_resource()
    content = b"<html><body>First version</body></html>"

    result = store_resource(resource, content)

    stored_file = tmp_path / result.storage_path

    assert stored_file.exists()
    assert stored_file.read_bytes() == content
    assert result.content_hash == calculate_sha256(content)


def test_store_resource_reuses_identical_content(tmp_path, monkeypatch):
    monkeypatch.setenv("ASPASIA_STORAGE_DIR", str(tmp_path))

    first_resource = create_resource()
    second_resource = create_resource()

    content = b"<html><body>Same content</body></html>"

    first_result = store_resource(first_resource, content)
    second_result = store_resource(second_resource, content)

    assert first_result.storage_path == second_result.storage_path
    assert first_result.content_hash == second_result.content_hash

    stored_files = list(tmp_path.rglob("*.html"))
    assert len(stored_files) == 1


def test_store_resource_preserves_different_versions(tmp_path, monkeypatch):
    monkeypatch.setenv("ASPASIA_STORAGE_DIR", str(tmp_path))

    resource = create_resource()

    first_content = b"<html><body>Version 1</body></html>"
    second_content = b"<html><body>Version 2</body></html>"

    first_result = store_resource(resource, first_content)
    second_result = store_resource(resource, second_content)

    first_file = tmp_path / first_result.storage_path
    second_file = tmp_path / second_result.storage_path

    assert first_result.content_hash != second_result.content_hash
    assert first_result.storage_path != second_result.storage_path

    assert first_file.exists()
    assert second_file.exists()

    assert first_file.read_bytes() == first_content
    assert second_file.read_bytes() == second_content


def test_store_resource_rejects_empty_content():
    resource = create_resource()

    with pytest.raises(ValueError):
        store_resource(resource, b"")

def test_store_resource_handles_concurrent_identical_content(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ASPASIA_STORAGE_DIR", str(tmp_path))

    content = b"<html><body>Concurrent content</body></html>"

    barrier = Barrier(2)
    original_replace = storage.os.replace

    def synchronized_replace(source, destination):
        barrier.wait(timeout=3)
        return original_replace(source, destination)

    monkeypatch.setattr(
        storage.os,
        "replace",
        synchronized_replace,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(store_resource, create_resource(), content)
            for _ in range(2)
        ]

        results = [future.result() for future in futures]

    assert results[0].storage_path == results[1].storage_path
    assert results[0].content_hash == results[1].content_hash

    stored_file = tmp_path / results[0].storage_path

    assert stored_file.exists()
    assert stored_file.read_bytes() == content

    assert list(tmp_path.glob("*.tmp")) == []

def test_store_resource_removes_temporary_file_on_replace_failure(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ASPASIA_STORAGE_DIR", str(tmp_path))

    def failing_replace(source, destination):
        raise OSError("Simulated storage failure")

    monkeypatch.setattr(
        storage.os,
        "replace",
        failing_replace,
    )

    with pytest.raises(OSError):
        store_resource(
            create_resource(),
            b"<html>Some content</html>",
        )

    assert list(tmp_path.glob("*.tmp")) == []
