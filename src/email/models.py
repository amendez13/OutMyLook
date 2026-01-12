"""Pydantic models for email data."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


def _get_attr(source: Any, *names: str, default: Any = None) -> Any:
    """Read attribute or dict key from a source object."""
    if source is None:
        return default
    for name in names:
        if isinstance(source, dict) and name in source:
            return source[name]
        if hasattr(source, name):
            return getattr(source, name)
    return default


def _normalize_datetime(value: Any) -> Any:
    """Normalize ISO timestamps so Pydantic can parse them."""
    if isinstance(value, str) and value.endswith("Z"):
        return value.replace("Z", "+00:00")
    return value


class EmailAddress(BaseModel):
    """Email address information."""

    address: str
    name: Optional[str] = None

    @classmethod
    def from_graph(cls, source: Any) -> "EmailAddress":
        """Create an EmailAddress from a Graph recipient or email address payload."""
        email_address = _get_attr(source, "email_address", "emailAddress", default=source)
        address = _get_attr(email_address, "address", default=None)
        name = _get_attr(email_address, "name", default=None)
        if not address:
            raise ValueError("Missing sender email address")
        return cls(address=address, name=name)


class Email(BaseModel):
    """Email model for fetched messages."""

    id: str
    subject: Optional[str] = None
    sender: EmailAddress
    received_at: datetime
    body_preview: str
    body_content: Optional[str] = None
    is_read: bool
    has_attachments: bool
    folder_id: str

    @classmethod
    def from_graph_message(cls, message: Any, folder_id: Optional[str] = None) -> "Email":
        """Create an Email model from a Graph message object or dict."""
        sender_source = _get_attr(message, "sender", "from_", "from", default=None)
        sender = EmailAddress.from_graph(sender_source) if sender_source else EmailAddress(address="unknown")

        received_at = _normalize_datetime(_get_attr(message, "received_date_time", "receivedDateTime", default=None))
        if received_at is None:
            raise ValueError("Missing receivedDateTime on message")

        body = _get_attr(message, "body", default=None)
        body_content = _get_attr(body, "content", default=None)

        folder_value = _get_attr(message, "parent_folder_id", "parentFolderId", default=None) or folder_id
        if folder_value is None:
            raise ValueError("Missing parentFolderId on message")

        return cls(
            id=_get_attr(message, "id"),
            subject=_get_attr(message, "subject", default=None),
            sender=sender,
            received_at=received_at,
            body_preview=_get_attr(message, "body_preview", "bodyPreview", default=""),
            body_content=body_content,
            is_read=bool(_get_attr(message, "is_read", "isRead", default=False)),
            has_attachments=bool(_get_attr(message, "has_attachments", "hasAttachments", default=False)),
            folder_id=folder_value,
        )


class MailFolder(BaseModel):
    """Mail folder metadata."""

    id: str
    display_name: str
    parent_folder_id: Optional[str] = None
    child_folder_count: int = 0
    total_item_count: int = 0
    unread_item_count: int = 0

    @classmethod
    def from_graph_folder(cls, folder: Any) -> "MailFolder":
        """Create a MailFolder model from a Graph folder payload."""
        return cls(
            id=_get_attr(folder, "id"),
            display_name=_get_attr(folder, "display_name", "displayName", default=""),
            parent_folder_id=_get_attr(folder, "parent_folder_id", "parentFolderId", default=None),
            child_folder_count=int(_get_attr(folder, "child_folder_count", "childFolderCount", default=0)),
            total_item_count=int(_get_attr(folder, "total_item_count", "totalItemCount", default=0)),
            unread_item_count=int(_get_attr(folder, "unread_item_count", "unreadItemCount", default=0)),
        )
