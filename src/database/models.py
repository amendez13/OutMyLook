"""SQLAlchemy ORM models for persisted email data."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for ORM models."""


class EmailModel(Base):
    """Persisted email metadata."""

    __tablename__ = "emails"
    __table_args__ = (
        Index("idx_emails_sender", "sender_email"),
        Index("idx_emails_received", "received_at"),
        Index("idx_emails_folder", "folder_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    subject: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sender_email: Mapped[str] = mapped_column(String, nullable=False)
    sender_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    body_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    folder_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    attachments: Mapped[List["AttachmentModel"]] = relationship(
        back_populates="email",
        cascade="all, delete-orphan",
    )


class AttachmentModel(Base):
    """Persisted attachment metadata."""

    __tablename__ = "attachments"
    __table_args__ = (Index("idx_attachments_email", "email_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email_id: Mapped[str] = mapped_column(String, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    local_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    email: Mapped[EmailModel] = relationship(back_populates="attachments")
