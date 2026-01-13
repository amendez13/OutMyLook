"""Tests for attachment handling."""

import base64
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.attachments.handler import AttachmentHandler
from src.attachments.models import Attachment, _get_attr


@pytest.mark.asyncio
async def test_list_attachments_saves_metadata(tmp_path: Path) -> None:
    """list_attachments should map payloads and save metadata."""
    graph_client = MagicMock()

    attachment = MagicMock()
    attachment.id = "att-1"
    attachment.name = "file.txt"
    attachment.content_type = "text/plain"
    attachment.size = 12

    response = MagicMock()
    response.value = [attachment]

    attachments_request = MagicMock()
    attachments_request.get = AsyncMock(return_value=response)

    message_request = MagicMock()
    message_request.attachments = attachments_request

    graph_client.me.messages.by_message_id.return_value = message_request

    repository = MagicMock()
    repository.save_metadata = AsyncMock()

    handler = AttachmentHandler(graph_client, tmp_path, repository)
    result = await handler.list_attachments("email-1")

    assert result == [Attachment(id="att-1", name="file.txt", content_type="text/plain", size=12)]
    repository.save_metadata.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_attachment_writes_file(tmp_path: Path) -> None:
    """download_attachment should write decoded content and update repository."""
    graph_client = MagicMock()

    content = base64.b64encode(b"hello").decode("ascii")
    attachment = MagicMock()
    attachment.id = "att-2"
    attachment.name = "report.txt"
    attachment.content_bytes = None
    attachment.contentBytes = content
    attachment.content_type = "text/plain"
    attachment.size = 5

    attachment_request = MagicMock()
    attachment_request.get = AsyncMock(return_value=attachment)

    attachments_request = MagicMock()
    attachments_request.by_attachment_id.return_value = attachment_request

    message_request = MagicMock()
    message_request.attachments = attachments_request

    graph_client.me.messages.by_message_id.return_value = message_request

    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=None)
    repository.save_metadata = AsyncMock()
    repository.mark_downloaded = AsyncMock()

    handler = AttachmentHandler(graph_client, tmp_path, repository)
    path = await handler.download_attachment("email-1", "att-2")

    assert path.exists()
    assert path.read_bytes() == b"hello"
    repository.save_metadata.assert_awaited_once()
    repository.mark_downloaded.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_attachment_skips_existing(tmp_path: Path) -> None:
    """download_attachment should return existing path when already downloaded."""
    graph_client = MagicMock()

    existing_path = tmp_path / "email-1" / "existing.txt"
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text("done")

    stored = MagicMock()
    stored.local_path = str(existing_path)

    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=stored)

    handler = AttachmentHandler(graph_client, tmp_path, repository)
    path = await handler.download_attachment("email-1", "att-3")

    assert path == existing_path


@pytest.mark.asyncio
async def test_download_attachment_handles_conflicts(tmp_path: Path) -> None:
    """download_attachment should create unique filenames when conflicts exist."""
    graph_client = MagicMock()

    content = base64.b64encode(b"data").decode("ascii")
    attachment = MagicMock()
    attachment.id = "att-4"
    attachment.name = "dup.txt"
    attachment.content_bytes = None
    attachment.contentBytes = content
    attachment.content_type = None
    attachment.size = None

    attachment_request = MagicMock()
    attachment_request.get = AsyncMock(return_value=attachment)

    attachments_request = MagicMock()
    attachments_request.by_attachment_id.return_value = attachment_request

    message_request = MagicMock()
    message_request.attachments = attachments_request

    graph_client.me.messages.by_message_id.return_value = message_request

    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=None)
    repository.save_metadata = AsyncMock()
    repository.mark_downloaded = AsyncMock()

    handler = AttachmentHandler(graph_client, tmp_path, repository)

    existing_dir = tmp_path / "email-1"
    existing_dir.mkdir(parents=True, exist_ok=True)
    (existing_dir / "dup.txt").write_text("old")

    path = await handler.download_attachment("email-1", "att-4")

    assert path.name == "dup_1.txt"


@pytest.mark.asyncio
async def test_list_attachments_skips_invalid_payload(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """list_attachments should skip items with missing required fields."""
    graph_client = MagicMock()

    attachment = MagicMock()
    attachment.id = None
    attachment.name = None

    response = MagicMock()
    response.value = [attachment]

    attachments_request = MagicMock()
    attachments_request.get = AsyncMock(return_value=response)

    message_request = MagicMock()
    message_request.attachments = attachments_request

    graph_client.me.messages.by_message_id.return_value = message_request

    repository = MagicMock()
    repository.save_metadata = AsyncMock()

    handler = AttachmentHandler(graph_client, tmp_path, repository)

    with caplog.at_level(logging.WARNING):
        result = await handler.list_attachments("email-1")

    assert result == []
    repository.save_metadata.assert_not_called()
    assert "Skipping attachment due to mapping error" in caplog.text


def test_extract_collection_variants() -> None:
    """_extract_collection should normalize response shapes."""
    assert AttachmentHandler._extract_collection(None) == []
    assert AttachmentHandler._extract_collection(["a", "b"]) == ["a", "b"]
    assert AttachmentHandler._extract_collection(SimpleNamespace(value=None)) == []
    assert AttachmentHandler._extract_collection(SimpleNamespace(value=("x", "y"))) == ["x", "y"]


def test_extract_content_bytes_prefers_content_bytes() -> None:
    """_extract_content_bytes should decode content_bytes when provided."""
    payload = base64.b64encode(b"hello").decode("ascii")
    attachment = SimpleNamespace(content_bytes=payload)
    assert AttachmentHandler._extract_content_bytes(attachment) == b"hello"


def test_extract_content_bytes_handles_content_bytes_bytes() -> None:
    """_extract_content_bytes should accept raw bytes in content_bytes."""
    attachment = SimpleNamespace(content_bytes=b"raw")
    assert AttachmentHandler._extract_content_bytes(attachment) == b"raw"


def test_extract_content_bytes_handles_content_bytes_property() -> None:
    """_extract_content_bytes should decode contentBytes string payloads."""
    payload = base64.b64encode(b"hello").decode("ascii")
    attachment = SimpleNamespace(contentBytes=payload)
    assert AttachmentHandler._extract_content_bytes(attachment) == b"hello"


def test_extract_content_bytes_handles_content_bytes_bytes_property() -> None:
    """_extract_content_bytes should accept raw bytes in contentBytes."""
    attachment = SimpleNamespace(contentBytes=b"raw")
    assert AttachmentHandler._extract_content_bytes(attachment) == b"raw"


@pytest.mark.asyncio
async def test_download_attachment_value_requires_request_adapter(tmp_path: Path) -> None:
    """_download_attachment_value should raise without request_adapter."""
    graph_client = SimpleNamespace()
    repository = MagicMock()
    handler = AttachmentHandler(graph_client, tmp_path, repository)

    with pytest.raises(ValueError, match="content is not available"):
        await handler._download_attachment_value("email-1", "att-1")


@pytest.mark.asyncio
async def test_download_attachment_value_handles_empty_response(tmp_path: Path) -> None:
    """_download_attachment_value should raise when response content is empty."""
    request_adapter = MagicMock()
    request_adapter.send_primitive_async = AsyncMock(return_value=None)
    graph_client = SimpleNamespace(request_adapter=request_adapter)
    repository = MagicMock()
    handler = AttachmentHandler(graph_client, tmp_path, repository)

    with pytest.raises(ValueError, match="content is not available"):
        await handler._download_attachment_value("email-1", "att-1")


@pytest.mark.asyncio
async def test_download_attachment_value_handles_bytearray(tmp_path: Path) -> None:
    """_download_attachment_value should convert bytearray payloads to bytes."""
    request_adapter = MagicMock()
    request_adapter.send_primitive_async = AsyncMock(return_value=bytearray(b"data"))
    graph_client = SimpleNamespace(request_adapter=request_adapter)
    repository = MagicMock()
    handler = AttachmentHandler(graph_client, tmp_path, repository)

    result = await handler._download_attachment_value("email-1", "att-2")

    assert result == b"data"


@pytest.mark.asyncio
async def test_download_attachment_value_rejects_unexpected_type(tmp_path: Path) -> None:
    """_download_attachment_value should raise for unsupported payload types."""
    request_adapter = MagicMock()
    request_adapter.send_primitive_async = AsyncMock(return_value="text")
    graph_client = SimpleNamespace(request_adapter=request_adapter)
    repository = MagicMock()
    handler = AttachmentHandler(graph_client, tmp_path, repository)

    with pytest.raises(TypeError, match="Unsupported attachment content type"):
        await handler._download_attachment_value("email-1", "att-3")


def test_get_attachment_request_prefers_by_id(tmp_path: Path) -> None:
    """_get_attachment_request should use by_id when by_attachment_id is missing."""
    attachments_request = SimpleNamespace(by_id=MagicMock(return_value="by-id"))
    message_request = SimpleNamespace(attachments=attachments_request)
    messages = SimpleNamespace(by_message_id=MagicMock(return_value=message_request))
    graph_client = SimpleNamespace(me=SimpleNamespace(messages=messages))
    repository = MagicMock()
    handler = AttachmentHandler(graph_client, tmp_path, repository)

    result = handler._get_attachment_request("email-1", "att-1")

    assert result == "by-id"
    attachments_request.by_id.assert_called_once_with("att-1")


def test_get_attachment_request_uses_indexer(tmp_path: Path) -> None:
    """_get_attachment_request should use index access as a fallback."""

    class AttachmentsIndex:
        def __init__(self) -> None:
            self.used = None

        def __getitem__(self, key: str) -> str:
            self.used = key
            return f"item-{key}"

    attachments_request = AttachmentsIndex()
    message_request = SimpleNamespace(attachments=attachments_request)
    messages = SimpleNamespace(by_message_id=MagicMock(return_value=message_request))
    graph_client = SimpleNamespace(me=SimpleNamespace(messages=messages))
    repository = MagicMock()
    handler = AttachmentHandler(graph_client, tmp_path, repository)

    result = handler._get_attachment_request("email-1", "att-2")

    assert result == "item-att-2"
    assert attachments_request.used == "att-2"


def test_get_message_request_uses_by_id(tmp_path: Path) -> None:
    """_get_message_request should fall back to by_id when by_message_id is missing."""
    messages = SimpleNamespace(by_id=MagicMock(return_value="message-request"))
    graph_client = SimpleNamespace(me=SimpleNamespace(messages=messages))
    repository = MagicMock()
    handler = AttachmentHandler(graph_client, tmp_path, repository)

    result = handler._get_message_request("email-1")

    assert result == "message-request"
    messages.by_id.assert_called_once_with("email-1")


def test_ensure_unique_path_raises_after_max_attempts(tmp_path: Path) -> None:
    """_ensure_unique_path should fail when all candidate names exist."""
    target = tmp_path / "dup.txt"
    target.write_text("base")
    for counter in range(1, 1001):
        (tmp_path / f"dup_{counter}.txt").write_text("x")

    with pytest.raises(RuntimeError, match="Unable to resolve unique path"):
        AttachmentHandler._ensure_unique_path(target)


@pytest.mark.asyncio
async def test_download_attachment_falls_back_to_value_endpoint(tmp_path: Path) -> None:
    """download_attachment should fetch content via $value when contentBytes is missing."""
    graph_client = MagicMock()

    attachment = MagicMock()
    attachment.id = "att-5"
    attachment.name = "large.bin"
    attachment.content_bytes = None
    attachment.contentBytes = None
    attachment.content_type = "application/octet-stream"
    attachment.size = 4

    attachment_request = MagicMock()
    attachment_request.get = AsyncMock(return_value=attachment)

    attachments_request = MagicMock()
    attachments_request.by_attachment_id.return_value = attachment_request

    message_request = MagicMock()
    message_request.attachments = attachments_request

    graph_client.me.messages.by_message_id.return_value = message_request
    graph_client.request_adapter = MagicMock()
    graph_client.request_adapter.send_primitive_async = AsyncMock(return_value=b"data")

    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=None)
    repository.save_metadata = AsyncMock()
    repository.mark_downloaded = AsyncMock()

    handler = AttachmentHandler(graph_client, tmp_path, repository)
    path = await handler.download_attachment("email-1", "att-5")

    assert path.exists()
    assert path.read_bytes() == b"data"
    graph_client.request_adapter.send_primitive_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_all_for_email_returns_paths(tmp_path: Path) -> None:
    """download_all_for_email should download each attachment and return paths."""
    graph_client = MagicMock()
    repository = MagicMock()
    handler = AttachmentHandler(graph_client, tmp_path, repository)

    attachments = [Attachment(id="a1", name="one.txt"), Attachment(id="a2", name="two.txt")]
    handler.list_attachments = AsyncMock(return_value=attachments)
    path_one = tmp_path / "one.txt"
    path_two = tmp_path / "two.txt"
    handler.download_attachment = AsyncMock(side_effect=[path_one, path_two])

    result = await handler.download_all_for_email("email-2")

    assert result == [path_one, path_two]
    handler.download_attachment.assert_has_awaits([call("email-2", "a1", "one.txt"), call("email-2", "a2", "two.txt")])


@pytest.mark.asyncio
async def test_download_all_for_email_empty_list(tmp_path: Path) -> None:
    """download_all_for_email should return an empty list when no attachments exist."""
    graph_client = MagicMock()
    repository = MagicMock()
    handler = AttachmentHandler(graph_client, tmp_path, repository)

    handler.list_attachments = AsyncMock(return_value=[])
    handler.download_attachment = AsyncMock()

    result = await handler.download_all_for_email("email-3")

    assert result == []
    handler.download_attachment.assert_not_called()


@pytest.mark.asyncio
async def test_download_all_for_email_propagates_errors(tmp_path: Path) -> None:
    """download_all_for_email should raise if any attachment download fails."""
    graph_client = MagicMock()
    repository = MagicMock()
    handler = AttachmentHandler(graph_client, tmp_path, repository)

    attachments = [Attachment(id="a1", name="one.txt"), Attachment(id="a2", name="two.txt")]
    handler.list_attachments = AsyncMock(return_value=attachments)
    handler.download_attachment = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await handler.download_all_for_email("email-4")


def test_extract_content_bytes_missing() -> None:
    """_extract_content_bytes should raise when no content is available."""
    attachment = SimpleNamespace()
    with pytest.raises(ValueError, match="content is not available"):
        AttachmentHandler._extract_content_bytes(attachment)


def test_extract_content_bytes_unsupported_type() -> None:
    """_extract_content_bytes should raise for unsupported content types."""
    attachment = SimpleNamespace(contentBytes=123)
    with pytest.raises(TypeError, match="Unsupported"):
        AttachmentHandler._extract_content_bytes(attachment)


def test_get_attr_handles_sources() -> None:
    """_get_attr should read from dicts, objects, or defaults."""
    assert _get_attr(None, "id", default="x") == "x"
    assert _get_attr({"id": "a"}, "id", default=None) == "a"
    assert _get_attr(SimpleNamespace(name="file"), "name", default=None) == "file"
    assert _get_attr(SimpleNamespace(other="x"), "name", default="fallback") == "fallback"


def test_from_graph_attachment_requires_id_and_name() -> None:
    """from_graph_attachment should raise when required fields are missing."""
    with pytest.raises(ValueError, match="Missing attachment id or name"):
        Attachment.from_graph_attachment(SimpleNamespace(id=None, name=None))


def test_from_graph_attachment_reads_content_type_and_size() -> None:
    """from_graph_attachment should map content type and size."""
    payload = {"id": "att-9", "name": "file.txt", "contentType": "text/plain", "size": 12}
    result = Attachment.from_graph_attachment(payload)
    assert result.content_type == "text/plain"
    assert result.size == 12
