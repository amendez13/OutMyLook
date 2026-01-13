"""Database repositories and session helpers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import TYPE_CHECKING, AsyncIterator, Iterable, Optional, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.database.models import Base, EmailModel

if TYPE_CHECKING:
    from src.email.models import Email


def build_async_db_url(database_url: str) -> str:
    """Convert a sync SQLAlchemy URL to an async-compatible URL."""
    if database_url.startswith("sqlite:///"):
        return database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    if database_url.startswith("sqlite://"):
        return database_url.replace("sqlite://", "sqlite+aiosqlite://")
    return database_url


def create_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine for the given database URL."""
    return create_async_engine(build_async_db_url(database_url), future=True)


async def init_db(engine: AsyncEngine) -> None:
    """Create database tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session(database_url: str) -> AsyncIterator[AsyncSession]:
    """Yield an async database session, creating tables on first use."""
    engine = create_engine(database_url)
    await init_db(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


class EmailRepository:
    """Repository for persisted emails."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, email: "Email") -> EmailModel:
        """Save or update a single email."""
        model = await self.get_by_id(email.id)
        if model is None:
            model = _build_email_model(email)
            self.session.add(model)
        else:
            _apply_email(model, email)
            self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def save_many(self, emails: list["Email"]) -> list[EmailModel]:
        """Bulk save emails with deduplication."""
        if not emails:
            return []

        unique_emails = _unique_emails(emails)
        existing = await self._fetch_existing(unique_emails.keys())
        models: list[EmailModel] = []
        new_models: list[EmailModel] = []

        for email_id, email in unique_emails.items():
            model = existing.get(email_id)
            if model is None:
                model = _build_email_model(email)
                self.session.add(model)
                new_models.append(model)
            else:
                _apply_email(model, email)
                self.session.add(model)
            models.append(model)

        await self.session.commit()
        for model in new_models:
            await self.session.refresh(model)
        return models

    async def get_by_id(self, email_id: str) -> Optional[EmailModel]:
        """Get email by Graph API ID."""
        result = await self.session.scalars(select(EmailModel).where(EmailModel.id == email_id))
        return cast(Optional[EmailModel], result.one_or_none())

    async def list_all(self, limit: int = 100, offset: int = 0, order_by: str = "received_at") -> list[EmailModel]:
        """List stored emails."""
        order_column = _resolve_order_column(order_by)
        stmt = select(EmailModel).order_by(order_column).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def search(
        self,
        sender: Optional[str] = None,
        subject: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> list[EmailModel]:
        """Search stored emails."""
        stmt = select(EmailModel)
        if sender:
            stmt = stmt.where(EmailModel.sender_email.contains(sender))
        if subject:
            stmt = stmt.where(EmailModel.subject.is_not(None)).where(EmailModel.subject.contains(subject))
        if date_from:
            stmt = stmt.where(EmailModel.received_at >= date_from)
        if date_to:
            stmt = stmt.where(EmailModel.received_at <= date_to)

        result = await self.session.execute(stmt.order_by(EmailModel.received_at))
        return list(result.scalars())

    async def _fetch_existing(self, email_ids: Iterable[str]) -> dict[str, EmailModel]:
        if not email_ids:
            return {}
        result = await self.session.execute(select(EmailModel).where(EmailModel.id.in_(list(email_ids))))
        return {model.id: model for model in result.scalars()}


def _build_email_model(email: "Email") -> EmailModel:
    model = EmailModel(
        id=email.id,
        subject=email.subject,
        sender_email=email.sender.address,
        sender_name=email.sender.name,
        received_at=email.received_at,
        body_preview=email.body_preview,
        body_content=email.body_content,
        is_read=email.is_read,
        has_attachments=email.has_attachments,
        folder_id=email.folder_id,
    )
    return model


def _apply_email(model: EmailModel, email: "Email") -> None:
    model.subject = email.subject
    model.sender_email = email.sender.address
    model.sender_name = email.sender.name
    model.received_at = email.received_at
    model.body_preview = email.body_preview
    model.body_content = email.body_content
    model.is_read = email.is_read
    model.has_attachments = email.has_attachments
    model.folder_id = email.folder_id


def _unique_emails(emails: list["Email"]) -> dict[str, "Email"]:
    unique: dict[str, Email] = {}
    for email in emails:
        unique[email.id] = email
    return unique


def _resolve_order_column(order_by: str):
    column = getattr(EmailModel, order_by, None)
    if column is None:
        raise ValueError(f"Invalid order_by column: {order_by}")
    return column
