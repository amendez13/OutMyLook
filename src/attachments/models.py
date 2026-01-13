"""Models for attachment metadata."""

from __future__ import annotations

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


class Attachment(BaseModel):
    """Attachment metadata from Microsoft Graph."""

    id: str
    name: str
    content_type: Optional[str] = None
    size: Optional[int] = None

    @classmethod
    def from_graph_attachment(cls, attachment: Any) -> "Attachment":
        """Create an Attachment from a Graph attachment payload."""
        attachment_id = _get_attr(attachment, "id", default=None)
        name = _get_attr(attachment, "name", default=None)
        if not attachment_id or not name:
            raise ValueError("Missing attachment id or name")
        content_type = _get_attr(attachment, "content_type", "contentType", default=None)
        size = _get_attr(attachment, "size", default=None)
        return cls(id=attachment_id, name=name, content_type=content_type, size=size)
