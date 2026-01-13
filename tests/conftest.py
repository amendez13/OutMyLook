"""Pytest configuration and shared fixtures."""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.repository import EmailRepository, get_session


@pytest.fixture
def sample_data() -> dict:
    """Provide sample data for tests.

    Returns:
        A dictionary with sample test data.
    """
    return {
        "key": "value",
        "number": 42,
        "items": ["a", "b", "c"],
    }


@pytest.fixture
def graph_user() -> SimpleNamespace:
    """Return a mocked Graph user payload."""
    return SimpleNamespace(
        display_name="Test User",
        user_principal_name="user@example.com",
    )


@pytest.fixture
def graph_message() -> SimpleNamespace:
    """Return a mocked Graph message payload."""
    return SimpleNamespace(
        id="msg-1",
        subject="Status update",
        sender=SimpleNamespace(
            email_address=SimpleNamespace(address="sender@example.com", name="Sender"),
        ),
        received_date_time=datetime(2024, 1, 5, 12, 30, tzinfo=timezone.utc),
        body_preview="Preview text",
        body=SimpleNamespace(content="Body text"),
        is_read=False,
        has_attachments=True,
        parent_folder_id="inbox",
    )


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Yield an in-memory async database session."""
    async with get_session("sqlite:///:memory:") as session:
        yield session


@pytest.fixture
async def email_repository(db_session: AsyncSession) -> EmailRepository:
    """Return an EmailRepository bound to the shared session."""
    return EmailRepository(db_session)
