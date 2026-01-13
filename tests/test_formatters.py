"""Tests for CLI formatters."""

from datetime import datetime, timezone
from types import SimpleNamespace

from rich.panel import Panel

from src.cli.formatters import (
    _format_bool,
    _format_datetime,
    _format_sender,
    build_email_table,
    build_status_panel,
    format_bytes,
)


def test_build_email_table_includes_columns() -> None:
    email = SimpleNamespace(
        id="email-1",
        subject=None,
        sender_name="Alice",
        sender_email="alice@example.com",
        received_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        is_read=True,
        has_attachments=False,
    )
    table = build_email_table([email], title="Emails", include_id=True, include_read=True)

    headers = [column.header for column in table.columns]
    assert headers[:2] == ["ID", "From"]
    assert table.row_count == 1


def test_build_status_panel() -> None:
    panel = build_status_panel([("Authentication", "✓")], title="Status")
    assert isinstance(panel, Panel)
    assert panel.title == "Status"


def test_format_bytes_formats_units() -> None:
    assert format_bytes(10) == "10 B"
    assert format_bytes(2048).endswith("KB")


def test_format_sender_variants() -> None:
    sender = SimpleNamespace(name="Sender Name", address="sender@example.com")
    email_with_sender = SimpleNamespace(sender=sender)
    assert _format_sender(email_with_sender) == "Sender Name"

    email_with_name = SimpleNamespace(sender=None, sender_name="Named", sender_email="a@example.com")
    assert _format_sender(email_with_name) == "Named"

    email_with_email = SimpleNamespace(sender=None, sender_name=None, sender_email="a@example.com")
    assert _format_sender(email_with_email) == "a@example.com"

    assert _format_sender(SimpleNamespace(sender=None, sender_name=None, sender_email=None)) == "unknown"


def test_format_datetime_and_bool() -> None:
    assert _format_datetime(None) == "unknown"
    assert _format_datetime("2024") == "2024"
    assert _format_bool(True) == "Yes"
    assert _format_bool(False) == "No"
