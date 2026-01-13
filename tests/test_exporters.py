"""Tests for export utilities."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.cli.exporters import export_emails, serialize_email
from src.database.models import EmailModel


def make_email_model(email_id: str = "email-1") -> EmailModel:
    return EmailModel(
        id=email_id,
        subject="Hello",
        sender_email="sender@example.com",
        sender_name="Sender",
        received_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        body_preview="Preview",
        body_content="Body",
        is_read=False,
        has_attachments=True,
        folder_id="inbox",
    )


def test_serialize_email() -> None:
    email = make_email_model()
    data = serialize_email(email)
    assert data["id"] == email.id
    assert data["sender_email"] == email.sender_email
    assert data["received_at"] == email.received_at.isoformat()


def test_export_emails_json(tmp_path: Path) -> None:
    output_path = tmp_path / "emails.json"
    email = make_email_model()

    export_emails([email], output_path, "json")

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload[0]["id"] == "email-1"
    assert payload[0]["sender_email"] == "sender@example.com"


def test_export_emails_csv(tmp_path: Path) -> None:
    output_path = tmp_path / "emails.csv"
    email = make_email_model()

    export_emails([email], output_path, "csv")

    with output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["id"] == "email-1"
    assert rows[0]["sender_email"] == "sender@example.com"


def test_export_emails_csv_empty(tmp_path: Path) -> None:
    output_path = tmp_path / "empty.csv"

    export_emails([], output_path, "csv")

    contents = output_path.read_text(encoding="utf-8").strip()
    assert contents.startswith("id,subject,sender_email")


def test_export_emails_invalid_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported export format"):
        export_emails([], tmp_path / "out.txt", "txt")
