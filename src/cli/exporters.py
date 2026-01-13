"""Export utilities for CLI data output."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from src.database.models import EmailModel

SUPPORTED_FORMATS = {"json", "csv"}


def export_emails(emails: Iterable[EmailModel], output_path: Path, fmt: str) -> None:
    """Export emails to a JSON or CSV file."""
    format_lower = fmt.lower()
    if format_lower not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported export format: {fmt}")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    serialized = [serialize_email(email) for email in emails]

    if format_lower == "json":
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(serialized, handle, ensure_ascii=False, indent=2)
        return

    fieldnames = list(serialized[0].keys()) if serialized else list(_empty_export_fields().keys())
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if serialized:
            writer.writerows(serialized)


def serialize_email(email: EmailModel) -> dict[str, object]:
    """Serialize an EmailModel for exporting."""
    return {
        "id": email.id,
        "subject": email.subject,
        "sender_email": email.sender_email,
        "sender_name": email.sender_name,
        "received_at": email.received_at.isoformat() if email.received_at else None,
        "body_preview": email.body_preview,
        "body_content": email.body_content,
        "is_read": email.is_read,
        "has_attachments": email.has_attachments,
        "folder_id": email.folder_id,
    }


def _empty_export_fields() -> dict[str, object]:
    return {
        "id": None,
        "subject": None,
        "sender_email": None,
        "sender_name": None,
        "received_at": None,
        "body_preview": None,
        "body_content": None,
        "is_read": None,
        "has_attachments": None,
        "folder_id": None,
    }
