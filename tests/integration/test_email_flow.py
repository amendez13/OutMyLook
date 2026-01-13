"""Integration tests for end-to-end email fetch and persistence."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.database.repository import EmailRepository
from src.email.client import EmailClient


@pytest.mark.asyncio
async def test_email_flow_fetches_and_persists(db_session, graph_message) -> None:
    """list_emails should persist fetched emails into the database."""
    graph_client = MagicMock()

    response = SimpleNamespace(value=[graph_message])
    messages_request = MagicMock()
    messages_request.get = AsyncMock(return_value=response)

    folder_request = MagicMock()
    folder_request.messages = messages_request

    graph_client.me.mail_folders.by_id.return_value = folder_request

    repository = EmailRepository(db_session)
    client = EmailClient(graph_client, email_repository=repository)

    emails = await client.list_emails(folder="Inbox", limit=1, skip=0)

    assert len(emails) == 1
    stored = await repository.get_by_id(graph_message.id)
    assert stored is not None
    assert stored.subject == graph_message.subject
    assert stored.sender_email == graph_message.sender.email_address.address
