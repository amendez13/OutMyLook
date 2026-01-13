"""Rich formatters for CLI output."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional

from rich.panel import Panel
from rich.table import Table


def build_email_table(
    emails: Iterable[Any],
    *,
    title: str,
    include_id: bool = False,
    include_read: bool = True,
) -> Table:
    """Create a rich table for email listings."""
    table = Table(title=title)
    if include_id:
        table.add_column("ID", style="dim", overflow="fold")
    table.add_column("From", style="magenta")
    table.add_column("Subject", style="white")
    table.add_column("Date", style="cyan")
    if include_read:
        table.add_column("Read", justify="center")
    table.add_column("Attachments", justify="center")

    for email in emails:
        sender = _format_sender(email)
        subject = getattr(email, "subject", None) or "(no subject)"
        received_at = _format_datetime(getattr(email, "received_at", None))
        is_read = _format_bool(getattr(email, "is_read", False))
        has_attachments = _format_bool(getattr(email, "has_attachments", False))

        row = []
        if include_id:
            row.append(str(getattr(email, "id", "")))
        row.extend([sender, subject, received_at])
        if include_read:
            row.append(is_read)
        row.append(has_attachments)
        table.add_row(*row)

    return table


def build_status_panel(lines: Iterable[tuple[str, str]], *, title: str = "Status") -> Panel:
    """Build a formatted status panel from label/value pairs."""
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()
    for label, value in lines:
        table.add_row(label, value)
    return Panel.fit(table, title=title, border_style="blue")


def format_bytes(size_bytes: int) -> str:
    """Format bytes as human-readable text."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    units = ["KB", "MB", "GB", "TB", "PB"]
    size = float(size_bytes)
    for unit in units:
        size /= 1024
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} EB"


def _format_sender(email: Any) -> str:
    sender = getattr(email, "sender", None)
    if sender is not None:
        name = getattr(sender, "name", None)
        if name:
            return str(name)
        address = getattr(sender, "address", None)
        if address:
            return str(address)
    sender_name = getattr(email, "sender_name", None)
    sender_email = getattr(email, "sender_email", None)
    if sender_name:
        return str(sender_name)
    if sender_email:
        return str(sender_email)
    return "unknown"


def _format_datetime(value: Optional[datetime]) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if value is None:
        return "unknown"
    return str(value)


def _format_bool(value: Any) -> str:
    return "Yes" if bool(value) else "No"
