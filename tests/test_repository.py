"""Tests for database repository operations."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.attachments.models import Attachment
from src.database.repository import AttachmentRepository, EmailRepository, init_db
from src.email.models import Email, EmailAddress


def make_email(
    email_id: str,
    *,
    subject: str | None = "Subject",
    sender_email: str = "alice@example.com",
    sender_name: str = "Alice",
    received_at: datetime | None = None,
    is_read: bool = False,
    has_attachments: bool = False,
) -> Email:
    if received_at is None:
        received_at = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    return Email(
        id=email_id,
        subject=subject,
        sender=EmailAddress(address=sender_email, name=sender_name),
        received_at=received_at,
        body_preview="Preview",
        body_content="Body",
        is_read=is_read,
        has_attachments=has_attachments,
        folder_id="inbox",
    )


@pytest.fixture
async def session(tmp_path: Path):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'repo.db'}"
    engine = create_async_engine(db_url)
    await init_db(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_save_and_get(session) -> None:
    """save should insert and get_by_id should return the email."""
    repo = EmailRepository(session)
    email = make_email("id-1")

    saved = await repo.save(email)
    fetched = await repo.get_by_id("id-1")

    assert saved.id == "id-1"
    assert fetched is not None
    assert fetched.subject == "Subject"


@pytest.mark.asyncio
async def test_save_updates_existing(session) -> None:
    """save should update existing emails."""
    repo = EmailRepository(session)
    email = make_email("id-2", subject="Initial")
    await repo.save(email)

    updated = make_email("id-2", subject="Updated")
    await repo.save(updated)

    fetched = await repo.get_by_id("id-2")
    assert fetched is not None
    assert fetched.subject == "Updated"


@pytest.mark.asyncio
async def test_save_many_deduplicates(session) -> None:
    """save_many should deduplicate and return unique models."""
    repo = EmailRepository(session)
    emails = [
        make_email("id-3", subject="One"),
        make_email("id-4", subject="Two"),
        make_email("id-3", subject="Updated"),
    ]

    saved = await repo.save_many(emails)

    assert len(saved) == 2
    all_emails = await repo.list_all(limit=10)
    assert {email.id for email in all_emails} == {"id-3", "id-4"}


@pytest.mark.asyncio
async def test_save_many_updates_existing(session) -> None:
    """save_many should update existing emails."""
    repo = EmailRepository(session)
    await repo.save(make_email("id-9", subject="Original"))

    updated = make_email("id-9", subject="Revised")
    saved = await repo.save_many([updated])

    assert len(saved) == 1
    fetched = await repo.get_by_id("id-9")
    assert fetched is not None
    assert fetched.subject == "Revised"


@pytest.mark.asyncio
async def test_save_many_empty_returns_empty(session) -> None:
    """save_many should return an empty list when given no emails."""
    repo = EmailRepository(session)

    result = await repo.save_many([])

    assert result == []


@pytest.mark.asyncio
async def test_list_all_pagination_and_order(session) -> None:
    """list_all should honor ordering and pagination."""
    repo = EmailRepository(session)
    first = make_email("id-5", received_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc))
    second = make_email("id-6", received_at=datetime(2024, 1, 2, 8, 0, tzinfo=timezone.utc))
    await repo.save_many([second, first])

    results = await repo.list_all(limit=1, offset=0, order_by="received_at")
    assert len(results) == 1
    assert results[0].id == "id-5"


@pytest.mark.asyncio
async def test_list_all_invalid_order_by(session) -> None:
    """list_all should reject invalid order_by values."""
    repo = EmailRepository(session)

    with pytest.raises(ValueError, match="Invalid order_by column"):
        await repo.list_all(order_by="not_a_column")


@pytest.mark.asyncio
async def test_search_filters(session) -> None:
    """search should filter by sender, subject, and date range."""
    repo = EmailRepository(session)
    base_time = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    early = make_email(
        "id-7",
        sender_email="boss@company.com",
        subject="Invoice",
        received_at=base_time,
        is_read=False,
        has_attachments=True,
    )
    later = make_email(
        "id-8",
        sender_email="friend@example.com",
        subject="Hello there",
        received_at=base_time + timedelta(days=2),
        is_read=True,
        has_attachments=False,
    )
    null_subject = make_email(
        "id-9",
        subject=None,
        received_at=base_time + timedelta(days=1),
        is_read=False,
        has_attachments=False,
    )
    await repo.save_many([early, later, null_subject])

    sender_results = await repo.search(sender="boss@company.com")
    assert [email.id for email in sender_results] == ["id-7"]

    subject_results = await repo.search(subject="Hello")
    assert [email.id for email in subject_results] == ["id-8"]

    from_results = await repo.search(date_from=base_time + timedelta(days=1))
    assert [email.id for email in from_results] == ["id-9", "id-8"]

    to_results = await repo.search(date_to=base_time + timedelta(days=1))
    assert [email.id for email in to_results] == ["id-7", "id-9"]

    unread_results = await repo.search(is_read=False)
    assert [email.id for email in unread_results] == ["id-7", "id-9"]

    attachments_results = await repo.search(has_attachments=True)
    assert [email.id for email in attachments_results] == ["id-7"]


@pytest.mark.asyncio
async def test_fetch_existing_empty(session) -> None:
    """_fetch_existing should return empty dict for empty IDs."""
    repo = EmailRepository(session)

    result = await repo._fetch_existing([])

    assert result == {}


@pytest.mark.asyncio
async def test_attachment_repository_save_and_list(session) -> None:
    """save_metadata should store attachments and list_for_email should retrieve them."""
    repo = AttachmentRepository(session)
    attachments = [Attachment(id="att-1", name="file.txt", content_type="text/plain", size=12)]

    saved = await repo.save_metadata("email-1", attachments)

    assert len(saved) == 1
    listed = await repo.list_for_email("email-1")
    assert [attachment.id for attachment in listed] == ["att-1"]


@pytest.mark.asyncio
async def test_attachment_repository_updates_existing(session) -> None:
    """save_metadata should update existing attachment metadata."""
    repo = AttachmentRepository(session)
    await repo.save_metadata("email-1", [Attachment(id="att-2", name="old.txt", content_type=None, size=1)])

    updated = await repo.save_metadata("email-1", [Attachment(id="att-2", name="new.txt", content_type=None, size=5)])

    assert updated[0].name == "new.txt"


@pytest.mark.asyncio
async def test_attachment_repository_mark_downloaded(session) -> None:
    """mark_downloaded should persist local path and timestamp."""
    repo = AttachmentRepository(session)
    await repo.save_metadata("email-1", [Attachment(id="att-3", name="file.txt", content_type=None, size=1)])

    downloaded = await repo.mark_downloaded("att-3", "/tmp/file.txt", datetime.now(timezone.utc))

    assert downloaded is not None
    assert downloaded.local_path == "/tmp/file.txt"
