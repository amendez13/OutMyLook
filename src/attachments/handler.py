"""Attachment download and management."""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, cast

from kiota_abstractions.method import Method
from kiota_abstractions.request_information import RequestInformation
from msgraph import GraphServiceClient
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn

from src.attachments.models import Attachment
from src.database.repository import AttachmentRepository

logger = logging.getLogger(__name__)


class AttachmentHandler:
    """Handle listing and downloading attachments."""

    def __init__(self, graph_client: GraphServiceClient, storage_dir: Path, repository: AttachmentRepository):
        self._graph_client = graph_client
        self._storage_dir = storage_dir.expanduser()
        self._repository = repository

    async def download_attachment(self, email_id: str, attachment_id: str, filename: Optional[str] = None) -> Path:
        """Download single attachment and return local path."""
        stored = await self._repository.get_by_id(attachment_id)
        if stored and stored.local_path:
            existing_path = Path(stored.local_path).expanduser()
            if existing_path.exists():
                return existing_path

        attachment_request = self._get_attachment_request(email_id, attachment_id)
        attachment = await attachment_request.get()
        attachment_model = Attachment.from_graph_attachment(attachment)

        name = filename or attachment_model.name
        target_dir = self._storage_dir / email_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._ensure_unique_path(target_dir / name)

        content_bytes = await self._get_content_bytes(email_id, attachment_id, attachment)
        await self._write_with_progress(target_path, content_bytes, attachment_model.name)

        await self._repository.save_metadata(email_id, [attachment_model])
        await self._repository.mark_downloaded(
            attachment_model.id,
            str(target_path),
            datetime.now(timezone.utc),
        )

        return target_path

    async def download_all_for_email(self, email_id: str) -> list[Path]:
        """Download all attachments for an email."""
        attachments = await self.list_attachments(email_id)
        paths: list[Path] = []
        for attachment in attachments:
            paths.append(await self.download_attachment(email_id, attachment.id, attachment.name))
        return paths

    async def list_attachments(self, email_id: str) -> list[Attachment]:
        """List attachments for an email without downloading."""
        attachments_request = self._get_attachments_request(email_id)
        response = await attachments_request.get()
        items = self._extract_collection(response)
        attachments: list[Attachment] = []
        for item in items:
            try:
                attachments.append(Attachment.from_graph_attachment(item))
            except ValueError as exc:
                logger.warning("Skipping attachment due to mapping error: %s", exc)
        if attachments:
            await self._repository.save_metadata(email_id, attachments)
        return attachments

    def _get_attachments_request(self, email_id: str) -> Any:
        message_request = self._get_message_request(email_id)
        return message_request.attachments

    def _get_attachment_request(self, email_id: str, attachment_id: str) -> Any:
        attachments = self._get_attachments_request(email_id)
        if hasattr(attachments, "by_attachment_id"):
            return attachments.by_attachment_id(attachment_id)
        if hasattr(attachments, "by_id"):
            return attachments.by_id(attachment_id)
        return attachments[attachment_id]

    def _get_message_request(self, email_id: str) -> Any:
        messages = cast(Any, self._graph_client.me.messages)
        if hasattr(messages, "by_message_id"):
            return messages.by_message_id(email_id)
        return messages.by_id(email_id)

    @staticmethod
    def _extract_collection(response: Any) -> list[Any]:
        if response is None:
            return []
        if isinstance(response, list):
            return response
        value = getattr(response, "value", None)
        if value is None:
            return []
        return list(value)

    @staticmethod
    def _extract_content_bytes(attachment: Any) -> bytes:
        content = getattr(attachment, "content_bytes", None)
        if isinstance(content, (bytes, str)):
            return base64.b64decode(content) if isinstance(content, str) else content
        content = getattr(attachment, "contentBytes", None)
        if content is None:
            raise ValueError("Attachment content is not available for download")
        if isinstance(content, bytes):
            return content
        if isinstance(content, str):
            return base64.b64decode(content)
        raise TypeError("Unsupported attachment content type")

    async def _get_content_bytes(self, email_id: str, attachment_id: str, attachment: Any) -> bytes:
        try:
            return self._extract_content_bytes(attachment)
        except ValueError as exc:
            logger.info("Attachment content missing; fetching via $value endpoint: %s", exc)
            return await self._download_attachment_value(email_id, attachment_id)

    async def _download_attachment_value(self, email_id: str, attachment_id: str) -> bytes:
        request_adapter = getattr(self._graph_client, "request_adapter", None)
        if request_adapter is None:
            raise ValueError("Attachment content is not available for download")
        request_info = RequestInformation(
            Method.GET,
            "{+baseurl}/me/messages/{message%2Did}/attachments/{attachment%2Did}/$value",
            {"message%2Did": email_id, "attachment%2Did": attachment_id},
        )
        request_info.headers.try_add("Accept", "application/octet-stream")
        content = await request_adapter.send_primitive_async(request_info, "bytes", None)
        if content is None:
            raise ValueError("Attachment content is not available for download")
        if isinstance(content, bytearray):
            return bytes(content)
        if isinstance(content, bytes):
            return content
        raise TypeError("Unsupported attachment content type")

    @staticmethod
    def _ensure_unique_path(path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1
        max_attempts = 1000
        while counter <= max_attempts:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
        raise RuntimeError(f"Unable to resolve unique path for {path} after {max_attempts} attempts")

    @staticmethod
    async def _write_with_progress(path: Path, content: bytes, label: str) -> None:
        total = len(content)
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task_id = progress.add_task(f"Downloading: {label}", total=total)
            with path.open("wb") as handle:
                chunk_size = 64 * 1024
                for start in range(0, total, chunk_size):
                    chunk = content[slice(start, start + chunk_size)]
                    handle.write(chunk)
                    progress.update(task_id, advance=len(chunk))
