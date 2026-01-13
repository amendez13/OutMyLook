"""Tests for attachment handling."""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.attachments.handler import AttachmentHandler
from src.attachments.models import Attachment


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
