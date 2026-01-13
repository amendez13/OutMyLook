"""OData filter builder for email queries."""

from __future__ import annotations

from datetime import datetime, timezone


class EmailFilter:
    """Build OData filter strings for Microsoft Graph email queries."""

    def __init__(self) -> None:
        self._conditions: list[str] = []

    def from_address(self, email: str) -> "EmailFilter":
        """Filter by sender email address."""
        if not email or not email.strip():
            raise ValueError("Sender address cannot be empty.")
        self._conditions.append(f"from/emailAddress/address eq '{_escape_odata_string(email.strip())}'")
        return self

    def subject_contains(self, text: str) -> "EmailFilter":
        """Filter by subject containing text."""
        if not text or not text.strip():
            raise ValueError("Subject filter text cannot be empty.")
        self._conditions.append(f"contains(subject, '{_escape_odata_string(text.strip())}')")
        return self

    def received_after(self, dt: datetime) -> "EmailFilter":
        """Filter emails received after date."""
        self._conditions.append(f"receivedDateTime ge {_format_datetime(dt)}")
        return self

    def received_before(self, dt: datetime) -> "EmailFilter":
        """Filter emails received before date."""
        self._conditions.append(f"receivedDateTime le {_format_datetime(dt)}")
        return self

    def is_read(self, read: bool = True) -> "EmailFilter":
        """Filter by read status."""
        self._conditions.append(f"isRead eq {str(read).lower()}")
        return self

    def has_attachments(self, has: bool = True) -> "EmailFilter":
        """Filter by attachment presence."""
        self._conditions.append(f"hasAttachments eq {str(has).lower()}")
        return self

    def build(self) -> str:
        """Build OData filter string."""
        return " and ".join(self._conditions)


def _escape_odata_string(value: str) -> str:
    """Escape single quotes for OData string literals."""
    return value.replace("'", "''")


def _format_datetime(dt: datetime) -> str:
    """Format datetime in ISO 8601 with UTC Z suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    formatted = dt.isoformat()
    if formatted.endswith("+00:00"):
        formatted = formatted.replace("+00:00", "Z")
    return formatted
