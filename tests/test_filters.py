"""Tests for the email filter builder."""

from datetime import datetime, timedelta, timezone

import pytest

from src.email.filters import EmailFilter


def test_build_empty_returns_empty_string() -> None:
    """build should return empty string when no conditions are set."""
    assert EmailFilter().build() == ""


def test_from_and_subject_escape_quotes() -> None:
    """from_address and subject_contains should escape single quotes."""
    email_filter = EmailFilter().from_address("o'malley@example.com").subject_contains("it's here")
    assert email_filter.build() == ("from/emailAddress/address eq 'o''malley@example.com' and contains(subject, 'it''s here')")


def test_received_date_filters_format_utc() -> None:
    """received_after/received_before should format datetimes with Z suffix."""
    dt = datetime(2024, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=-5)))
    email_filter = EmailFilter().received_after(dt).received_before(dt)
    assert email_filter.build() == ("receivedDateTime ge 2024-01-01T17:00:00Z and receivedDateTime le 2024-01-01T17:00:00Z")


def test_read_and_attachment_filters() -> None:
    """is_read and has_attachments should set boolean filters."""
    email_filter = EmailFilter().is_read(False).has_attachments(True)
    assert email_filter.build() == "isRead eq false and hasAttachments eq true"


def test_from_address_empty_raises() -> None:
    """from_address should reject empty input."""
    with pytest.raises(ValueError, match="Sender address cannot be empty"):
        EmailFilter().from_address("   ")


def test_subject_empty_raises() -> None:
    """subject_contains should reject empty input."""
    with pytest.raises(ValueError, match="Subject filter text cannot be empty"):
        EmailFilter().subject_contains("")
