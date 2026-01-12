"""Tests for email models."""

from datetime import datetime, timezone

import pytest

from src.email.models import Email, EmailAddress, MailFolder


def test_email_address_from_graph_dict() -> None:
    """EmailAddress.from_graph should parse dict payloads."""
    payload = {"emailAddress": {"address": "alice@example.com", "name": "Alice"}}

    address = EmailAddress.from_graph(payload)

    assert address.address == "alice@example.com"
    assert address.name == "Alice"


def test_email_from_graph_message_maps_fields() -> None:
    """Email.from_graph_message should map core Graph fields."""
    message = {
        "id": "msg-1",
        "subject": "Hello",
        "sender": {"emailAddress": {"address": "alice@example.com", "name": "Alice"}},
        "receivedDateTime": "2024-01-01T12:00:00Z",
        "bodyPreview": "Preview",
        "body": {"content": "Full body"},
        "isRead": True,
        "hasAttachments": False,
        "parentFolderId": "inbox",
    }

    email = Email.from_graph_message(message)

    assert email.id == "msg-1"
    assert email.subject == "Hello"
    assert email.sender.address == "alice@example.com"
    assert email.body_preview == "Preview"
    assert email.body_content == "Full body"
    assert email.is_read is True
    assert email.has_attachments is False
    assert email.folder_id == "inbox"


def test_email_from_graph_message_accepts_datetime() -> None:
    """Email.from_graph_message should accept datetime values."""
    message = {
        "id": "msg-2",
        "subject": None,
        "sender": {"emailAddress": {"address": "bob@example.com"}},
        "receivedDateTime": datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc),
        "bodyPreview": "",
        "body": {"content": None},
        "isRead": False,
        "hasAttachments": True,
        "parentFolderId": "sentitems",
    }

    email = Email.from_graph_message(message)

    assert email.received_at == datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)
    assert email.sender.address == "bob@example.com"


def test_mail_folder_from_graph_folder() -> None:
    """MailFolder.from_graph_folder should map folder fields."""
    folder = {
        "id": "folder-1",
        "displayName": "Inbox",
        "parentFolderId": None,
        "childFolderCount": 0,
        "totalItemCount": 12,
        "unreadItemCount": 4,
    }

    model = MailFolder.from_graph_folder(folder)

    assert model.id == "folder-1"
    assert model.display_name == "Inbox"
    assert model.total_item_count == 12
    assert model.unread_item_count == 4


def test_email_address_missing_raises() -> None:
    """EmailAddress.from_graph should raise when address is missing."""
    with pytest.raises(ValueError, match="Missing sender email address"):
        EmailAddress.from_graph({"emailAddress": {"name": "No Address"}})
