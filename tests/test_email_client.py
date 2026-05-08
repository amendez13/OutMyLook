"""Tests for the email client wrapper."""

import logging
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kiota_abstractions.method import Method

from src.email.client import EmailClient
from src.email.filters import EmailFilter
from src.email.models import MailFolder


@pytest.mark.asyncio
async def test_list_emails_uses_pagination_and_maps() -> None:
    """list_emails should pass pagination and map messages to models."""
    graph_client = MagicMock()

    message = MagicMock()
    message.id = "msg-1"
    message.subject = "Hello"
    message.sender = MagicMock()
    message.sender.email_address = MagicMock()
    message.sender.email_address.address = "alice@example.com"
    message.sender.email_address.name = "Alice"
    message.received_date_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    message.body_preview = "Preview"
    message.body = MagicMock(content="Body")
    message.is_read = False
    message.has_attachments = True
    message.parent_folder_id = "inbox"

    response = MagicMock()
    response.value = [message]

    messages_request = MagicMock()
    messages_request.get = AsyncMock(return_value=response)

    folder_request = MagicMock()
    folder_request.messages = messages_request

    graph_client.me.mail_folders.by_id.return_value = folder_request

    client = EmailClient(graph_client)
    config = MagicMock()
    config.query_parameters = MagicMock(top=10, skip=5)

    with patch.object(client, "_build_messages_request_config", return_value=config):
        emails = await client.list_emails(folder="Inbox", limit=10, skip=5)

    messages_request.get.assert_awaited_with(request_configuration=config)
    graph_client.me.mail_folders.by_id.assert_called_with("inbox")
    assert len(emails) == 1
    assert emails[0].id == "msg-1"


@pytest.mark.asyncio
async def test_resolve_folder_id_matches_display_name() -> None:
    """_resolve_folder_id should match folder display names."""
    graph_client = MagicMock()
    client = EmailClient(graph_client)

    folder = MailFolder(id="folder-123", display_name="Custom")
    with patch.object(client, "list_folders", AsyncMock(return_value=[folder])):
        folder_id = await client._resolve_folder_id("Custom")

    assert folder_id == "folder-123"


@pytest.mark.asyncio
async def test_list_folders_maps_response() -> None:
    """list_folders should map Graph folder payloads."""
    graph_client = MagicMock()

    folder_payload = MagicMock()
    folder_payload.id = "folder-1"
    folder_payload.display_name = "Inbox"
    folder_payload.parent_folder_id = None
    folder_payload.child_folder_count = 0
    folder_payload.total_item_count = 5
    folder_payload.unread_item_count = 2

    response = MagicMock()
    response.value = [folder_payload]

    mail_folders_builder = MagicMock()
    mail_folders_builder.get = AsyncMock(return_value=response)

    graph_client.me.mail_folders = mail_folders_builder

    client = EmailClient(graph_client)
    config = MagicMock()

    with patch.object(client, "_build_folders_request_config", return_value=config):
        folders = await client.list_folders()

    mail_folders_builder.get.assert_awaited_with(request_configuration=config)
    assert folders[0].display_name == "Inbox"
    assert folders[0].unread_item_count == 2


@pytest.mark.asyncio
async def test_get_email_returns_model() -> None:
    """get_email should return a mapped Email model."""
    graph_client = MagicMock()

    message = MagicMock()
    message.id = "msg-2"
    message.subject = "Subject"
    message.sender = MagicMock()
    message.sender.email_address = MagicMock()
    message.sender.email_address.address = "bob@example.com"
    message.sender.email_address.name = None
    message.received_date_time = datetime(2024, 1, 3, 9, 0, tzinfo=timezone.utc)
    message.body_preview = "Preview"
    message.body = MagicMock(content="Body")
    message.is_read = True
    message.has_attachments = False
    message.parent_folder_id = "inbox"

    message_request = MagicMock()
    message_request.get = AsyncMock(return_value=message)

    graph_client.me.messages.by_message_id.return_value = message_request

    client = EmailClient(graph_client)
    email = await client.get_email("msg-2")

    graph_client.me.messages.by_message_id.assert_called_with("msg-2")
    assert email.subject == "Subject"


@pytest.mark.asyncio
async def test_list_emails_without_request_config_uses_default_get() -> None:
    """list_emails should call get without request configuration when none is built."""
    graph_client = MagicMock()

    message = MagicMock()
    message.id = "msg-3"
    message.subject = "Hello"
    message.sender = MagicMock()
    message.sender.email_address = MagicMock()
    message.sender.email_address.address = "alice@example.com"
    message.sender.email_address.name = "Alice"
    message.received_date_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    message.body_preview = "Preview"
    message.body = MagicMock(content="Body")
    message.is_read = False
    message.has_attachments = True
    message.parent_folder_id = "inbox"

    response = MagicMock()
    response.value = [message]

    messages_request = MagicMock()
    messages_request.get = AsyncMock(return_value=response)

    folder_request = MagicMock()
    folder_request.messages = messages_request

    graph_client.me.mail_folders.by_id.return_value = folder_request

    client = EmailClient(graph_client)

    with patch.object(client, "_build_messages_request_config", return_value=None):
        emails = await client.list_emails(folder="Inbox", limit=10, skip=0)

    messages_request.get.assert_awaited_once_with()
    assert len(emails) == 1


@pytest.mark.asyncio
async def test_list_emails_without_folder_uses_mailbox_messages() -> None:
    """list_emails should use the mailbox messages collection when folder is None."""
    graph_client = MagicMock()

    message = MagicMock()
    message.id = "msg-12"
    message.subject = "Hello"
    message.sender = MagicMock()
    message.sender.email_address = MagicMock()
    message.sender.email_address.address = "alice@example.com"
    message.sender.email_address.name = "Alice"
    message.received_date_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    message.body_preview = "Preview"
    message.body = MagicMock(content="Body")
    message.is_read = False
    message.has_attachments = True
    message.parent_folder_id = "inbox"

    response = MagicMock()
    response.value = [message]

    messages_request = MagicMock()
    messages_request.get = AsyncMock(return_value=response)
    graph_client.me.messages = messages_request

    client = EmailClient(graph_client)

    with patch.object(client, "_build_messages_request_config", return_value=None):
        emails = await client.list_emails(folder=None, limit=10, skip=0)

    messages_request.get.assert_awaited_once_with()
    assert len(emails) == 1


@pytest.mark.asyncio
async def test_list_emails_skips_invalid_message(caplog: pytest.LogCaptureFixture) -> None:
    """list_emails should skip invalid messages and log a warning."""
    graph_client = MagicMock()
    response = MagicMock()
    response.value = [MagicMock()]

    messages_request = MagicMock()
    messages_request.get = AsyncMock(return_value=response)

    folder_request = MagicMock()
    folder_request.messages = messages_request

    graph_client.me.mail_folders.by_id.return_value = folder_request

    client = EmailClient(graph_client)

    with (
        patch.object(client, "_build_messages_request_config", return_value=None),
        patch("src.email.client.Email.from_graph_message", side_effect=ValueError("bad message")),
        caplog.at_level(logging.WARNING),
    ):
        emails = await client.list_emails(folder="inbox", limit=1, skip=0)

    assert emails == []
    assert "Skipping message due to mapping error" in caplog.text


@pytest.mark.asyncio
async def test_list_emails_without_repository_returns_results() -> None:
    """list_emails should work when no repository is configured."""
    graph_client = MagicMock()

    message = MagicMock()
    message.id = "msg-9"
    message.subject = "Hello"
    message.sender = MagicMock()
    message.sender.email_address = MagicMock()
    message.sender.email_address.address = "alice@example.com"
    message.sender.email_address.name = "Alice"
    message.received_date_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    message.body_preview = "Preview"
    message.body = MagicMock(content="Body")
    message.is_read = False
    message.has_attachments = True
    message.parent_folder_id = "inbox"

    response = MagicMock()
    response.value = [message]

    messages_request = MagicMock()
    messages_request.get = AsyncMock(return_value=response)

    folder_request = MagicMock()
    folder_request.messages = messages_request

    graph_client.me.mail_folders.by_id.return_value = folder_request

    client = EmailClient(graph_client)

    with patch.object(client, "_build_messages_request_config", return_value=None):
        emails = await client.list_emails(folder="Inbox", limit=1, skip=0)

    assert len(emails) == 1


@pytest.mark.asyncio
async def test_list_emails_saves_to_repository() -> None:
    """list_emails should persist emails when a repository is configured."""
    graph_client = MagicMock()

    message = MagicMock()
    message.id = "msg-10"
    message.subject = "Hello"
    message.sender = MagicMock()
    message.sender.email_address = MagicMock()
    message.sender.email_address.address = "alice@example.com"
    message.sender.email_address.name = "Alice"
    message.received_date_time = datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)
    message.body_preview = "Preview"
    message.body = MagicMock(content="Body")
    message.is_read = False
    message.has_attachments = True
    message.parent_folder_id = "inbox"

    response = MagicMock()
    response.value = [message]

    messages_request = MagicMock()
    messages_request.get = AsyncMock(return_value=response)

    folder_request = MagicMock()
    folder_request.messages = messages_request

    graph_client.me.mail_folders.by_id.return_value = folder_request

    repository = MagicMock()
    repository.save_many = AsyncMock()

    client = EmailClient(graph_client, email_repository=repository)

    with patch.object(client, "_build_messages_request_config", return_value=None):
        emails = await client.list_emails(folder="Inbox", limit=1, skip=0)

    assert len(emails) == 1
    repository.save_many.assert_awaited_once_with(emails)


@pytest.mark.asyncio
async def test_list_emails_with_repository_empty_does_not_save() -> None:
    """list_emails should not save when there are no emails."""
    graph_client = MagicMock()

    response = MagicMock()
    response.value = []

    messages_request = MagicMock()
    messages_request.get = AsyncMock(return_value=response)

    folder_request = MagicMock()
    folder_request.messages = messages_request

    graph_client.me.mail_folders.by_id.return_value = folder_request

    repository = MagicMock()
    repository.save_many = AsyncMock()

    client = EmailClient(graph_client, email_repository=repository)

    with patch.object(client, "_build_messages_request_config", return_value=None):
        emails = await client.list_emails(folder="Inbox", limit=1, skip=0)

    assert emails == []
    repository.save_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_emails_save_raises_propagates() -> None:
    """list_emails should propagate repository errors."""
    graph_client = MagicMock()

    message = MagicMock()
    message.id = "msg-11"
    message.subject = "Hello"
    message.sender = MagicMock()
    message.sender.email_address = MagicMock()
    message.sender.email_address.address = "alice@example.com"
    message.sender.email_address.name = "Alice"
    message.received_date_time = datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)
    message.body_preview = "Preview"
    message.body = MagicMock(content="Body")
    message.is_read = False
    message.has_attachments = True
    message.parent_folder_id = "inbox"

    response = MagicMock()
    response.value = [message]

    messages_request = MagicMock()
    messages_request.get = AsyncMock(return_value=response)

    folder_request = MagicMock()
    folder_request.messages = messages_request

    graph_client.me.mail_folders.by_id.return_value = folder_request

    repository = MagicMock()
    repository.save_many = AsyncMock(side_effect=RuntimeError("db failure"))

    client = EmailClient(graph_client, email_repository=repository)

    with (
        patch.object(client, "_build_messages_request_config", return_value=None),
        pytest.raises(RuntimeError, match="db failure"),
    ):
        await client.list_emails(folder="Inbox", limit=1, skip=0)


@pytest.mark.asyncio
async def test_get_email_uses_by_id_when_missing_by_message_id() -> None:
    """get_email should use by_id when by_message_id is unavailable."""
    graph_client = MagicMock()

    message = MagicMock()
    message.id = "msg-4"
    message.subject = "Subject"
    message.sender = MagicMock()
    message.sender.email_address = MagicMock()
    message.sender.email_address.address = "bob@example.com"
    message.sender.email_address.name = None
    message.received_date_time = datetime(2024, 1, 3, 9, 0, tzinfo=timezone.utc)
    message.body_preview = "Preview"
    message.body = MagicMock(content="Body")
    message.is_read = True
    message.has_attachments = False
    message.parent_folder_id = "inbox"

    message_request = MagicMock()
    message_request.get = AsyncMock(return_value=message)

    messages_builder = SimpleNamespace(by_id=MagicMock(return_value=message_request))
    graph_client.me.messages = messages_builder

    client = EmailClient(graph_client)
    email = await client.get_email("msg-4")

    messages_builder.by_id.assert_called_with("msg-4")
    assert email.id == "msg-4"


def test_get_folder_messages_request_uses_by_mail_folder_id() -> None:
    """_get_folder_messages_request should use by_mail_folder_id when by_id is missing."""
    graph_client = MagicMock()
    folder_request = MagicMock()
    folder_request.messages = "messages"

    mail_folders = SimpleNamespace(by_mail_folder_id=MagicMock(return_value=folder_request))
    graph_client.me.mail_folders = mail_folders

    client = EmailClient(graph_client)
    messages = client._get_folder_messages_request("custom-folder")

    mail_folders.by_mail_folder_id.assert_called_with("custom-folder")
    assert messages == "messages"


@pytest.mark.asyncio
async def test_ensure_folder_returns_existing_match_case_insensitive() -> None:
    """ensure_folder should reuse an existing folder when names match."""
    client = EmailClient(MagicMock())
    folder = MailFolder(id="folder-1", display_name="Pre-Delete")

    with patch.object(client, "list_folders", AsyncMock(return_value=[folder])):
        resolved = await client.ensure_folder("pre-delete")

    assert resolved is folder


@pytest.mark.asyncio
async def test_ensure_folder_creates_and_refetches() -> None:
    """ensure_folder should create missing folders and return the created folder."""
    client = EmailClient(MagicMock())
    created_folder = MailFolder(id="folder-2", display_name="Pre-Delete")

    with (
        patch.object(client, "list_folders", AsyncMock(return_value=[])),
        patch.object(client, "_create_folder", AsyncMock(return_value=created_folder)) as create_folder,
    ):
        resolved = await client.ensure_folder("Pre-Delete")

    create_folder.assert_awaited_once_with("Pre-Delete")
    assert resolved == created_folder


@pytest.mark.asyncio
async def test_move_email_posts_move_request() -> None:
    """move_email should post a move request with the resolved destination ID."""
    request_adapter = MagicMock()
    request_adapter.send_primitive_async = AsyncMock(return_value=b"{}")
    graph_client = MagicMock(request_adapter=request_adapter)
    client = EmailClient(graph_client)

    with patch.object(client, "_resolve_folder_id", AsyncMock(return_value="folder-123")):
        await client.move_email("message-1", "Archive")

    request_info = request_adapter.send_primitive_async.await_args.args[0]
    assert request_info.http_method == Method.POST
    assert request_info.url_template == "{+baseurl}/me/messages/{message%2Did}/move"
    assert request_info.path_parameters["message%2Did"] == "message-1"
    assert b"folder-123" in request_info.content


@pytest.mark.asyncio
async def test_resolve_folder_prefers_existing_graph_folder_id() -> None:
    """resolve_folder should return an existing folder when the input is a Graph ID."""
    client = EmailClient(MagicMock())
    folder = MailFolder(id="folder-1", display_name="Nested")

    with (
        patch.object(client, "get_folder", AsyncMock(return_value=folder)) as get_folder,
        patch.object(client, "_resolve_folder_id", AsyncMock()) as resolve_folder_id,
        patch.object(client, "ensure_folder", AsyncMock()) as ensure_folder,
    ):
        resolved = await client.resolve_folder("folder-1")

    get_folder.assert_awaited_once_with("folder-1")
    resolve_folder_id.assert_not_awaited()
    ensure_folder.assert_not_awaited()
    assert resolved is folder


@pytest.mark.asyncio
async def test_resolve_folder_uses_well_known_alias_before_creating() -> None:
    """resolve_folder should use resolved well-known aliases before creating folders."""
    client = EmailClient(MagicMock())
    deleted_items = MailFolder(id="deleteditems", display_name="Deleted Items")

    with (
        patch.object(client, "get_folder", AsyncMock(side_effect=[None, deleted_items])) as get_folder,
        patch.object(client, "_resolve_folder_id", AsyncMock(return_value="deleteditems")) as resolve_folder_id,
        patch.object(client, "ensure_folder", AsyncMock()) as ensure_folder,
    ):
        resolved = await client.resolve_folder("deleted")

    assert get_folder.await_args_list[0].args == ("deleted",)
    assert get_folder.await_args_list[1].args == ("deleteditems",)
    resolve_folder_id.assert_awaited_once_with("deleted")
    ensure_folder.assert_not_awaited()
    assert resolved is deleted_items


@pytest.mark.asyncio
async def test_resolve_folder_creates_when_no_existing_folder_matches() -> None:
    """resolve_folder should create a folder only when nothing resolves."""
    client = EmailClient(MagicMock())
    created_folder = MailFolder(id="folder-2", display_name="Pre-Delete")

    with (
        patch.object(client, "get_folder", AsyncMock(return_value=None)) as get_folder,
        patch.object(client, "_resolve_folder_id", AsyncMock(return_value="Pre-Delete")) as resolve_folder_id,
        patch.object(client, "ensure_folder", AsyncMock(return_value=created_folder)) as ensure_folder,
    ):
        resolved = await client.resolve_folder("Pre-Delete")

    get_folder.assert_awaited_once_with("Pre-Delete")
    resolve_folder_id.assert_awaited_once_with("Pre-Delete")
    ensure_folder.assert_awaited_once_with("Pre-Delete")
    assert resolved is created_folder


@pytest.mark.asyncio
async def test_get_folder_returns_model() -> None:
    """get_folder should fetch and map a folder by Graph ID."""
    graph_client = MagicMock()

    folder_payload = MagicMock()
    folder_payload.id = "folder-1"
    folder_payload.display_name = "Nested"
    folder_payload.parent_folder_id = "parent-1"
    folder_payload.child_folder_count = 0
    folder_payload.total_item_count = 4
    folder_payload.unread_item_count = 1

    folder_request = MagicMock()
    folder_request.get = AsyncMock(return_value=folder_payload)
    graph_client.me.mail_folders.by_id.return_value = folder_request

    client = EmailClient(graph_client)
    folder = await client.get_folder("folder-1")

    graph_client.me.mail_folders.by_id.assert_called_with("folder-1")
    assert folder is not None
    assert folder.id == "folder-1"


@pytest.mark.asyncio
async def test_get_folder_returns_none_on_error() -> None:
    """get_folder should return None when the folder lookup fails."""
    graph_client = MagicMock()
    folder_request = MagicMock()
    folder_request.get = AsyncMock(side_effect=RuntimeError("missing"))
    graph_client.me.mail_folders.by_id.return_value = folder_request

    client = EmailClient(graph_client)
    folder = await client.get_folder("folder-1")

    assert folder is None


@pytest.mark.asyncio
async def test_resolve_folder_id_returns_well_known() -> None:
    """_resolve_folder_id should map well-known folders."""
    client = EmailClient(MagicMock())

    with patch.object(client, "list_folders", new_callable=AsyncMock) as list_folders:
        result = await client._resolve_folder_id("Sent Items")

    list_folders.assert_not_called()
    assert result == "sentitems"


@pytest.mark.asyncio
async def test_resolve_folder_id_returns_input_when_not_found() -> None:
    """_resolve_folder_id should return input when no folder matches."""
    client = EmailClient(MagicMock())

    with patch.object(client, "list_folders", AsyncMock(return_value=[])):
        result = await client._resolve_folder_id("Unknown")

    assert result == "Unknown"


@pytest.mark.asyncio
async def test_list_folders_without_request_config() -> None:
    """list_folders should call get without request configuration when none is built."""
    graph_client = MagicMock()

    folder_payload = MagicMock()
    folder_payload.id = "folder-2"
    folder_payload.display_name = "Inbox"
    folder_payload.parent_folder_id = None
    folder_payload.child_folder_count = 0
    folder_payload.total_item_count = 5
    folder_payload.unread_item_count = 2

    response = MagicMock()
    response.value = [folder_payload]

    mail_folders_builder = MagicMock()
    mail_folders_builder.get = AsyncMock(return_value=response)

    graph_client.me.mail_folders = mail_folders_builder

    client = EmailClient(graph_client)

    with patch.object(client, "_build_folders_request_config", return_value=None):
        folders = await client.list_folders()

    mail_folders_builder.get.assert_awaited_once_with()
    assert folders[0].id == "folder-2"


def test_build_messages_request_config_returns_none_when_builder_missing() -> None:
    """_build_messages_request_config should return None when builder is missing."""
    client = EmailClient(MagicMock())

    with patch.object(client, "_import_builder", return_value=None):
        config = client._build_messages_request_config(limit=10, skip=5)

    assert config is None


def test_build_messages_request_config_builds_query() -> None:
    """_build_messages_request_config should build request config with query params."""

    class DummyMessagesBuilder:
        class MessagesRequestBuilderGetQueryParameters:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs

        class MessagesRequestBuilderGetRequestConfiguration:
            def __init__(self, query_parameters) -> None:
                self.query_parameters = query_parameters

    client = EmailClient(MagicMock())

    with patch.object(client, "_import_builder", return_value=DummyMessagesBuilder):
        config = client._build_messages_request_config(limit=5, skip=10, filter_query="isRead eq true")

    assert config.query_parameters.kwargs["top"] == 5
    assert config.query_parameters.kwargs["skip"] == 10
    assert config.query_parameters.kwargs["filter"] == "isRead eq true"
    assert "subject" in config.query_parameters.kwargs["select"]
    assert "receivedDateTime desc" in config.query_parameters.kwargs["orderby"]


@pytest.mark.asyncio
async def test_list_emails_passes_filter_query() -> None:
    """list_emails should pass filters into request configuration."""
    graph_client = MagicMock()
    messages_request = MagicMock()
    messages_request.get = AsyncMock(return_value=MagicMock(value=[]))
    folder_request = MagicMock(messages=messages_request)
    graph_client.me.mail_folders.by_id.return_value = folder_request

    client = EmailClient(graph_client)
    email_filter = EmailFilter().subject_contains("hello")

    config = MagicMock()
    with patch.object(client, "_build_messages_request_config", return_value=config) as mock_config:
        await client.list_emails(folder="Inbox", limit=5, skip=0, email_filter=email_filter)

    mock_config.assert_called_with(
        limit=5,
        skip=0,
        filter_query=email_filter.build(),
        include_orderby=True,
    )


def test_build_folders_request_config_returns_none_when_builder_missing() -> None:
    """_build_folders_request_config should return None when builder is missing."""
    client = EmailClient(MagicMock())

    with patch.object(client, "_import_builder", return_value=None):
        config = client._build_folders_request_config()

    assert config is None


def test_build_folders_request_config_builds_query() -> None:
    """_build_folders_request_config should build request config with query params."""

    class DummyFoldersBuilder:
        class MailFoldersRequestBuilderGetQueryParameters:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs

        class MailFoldersRequestBuilderGetRequestConfiguration:
            def __init__(self, query_parameters) -> None:
                self.query_parameters = query_parameters

    client = EmailClient(MagicMock())

    with patch.object(client, "_import_builder", return_value=DummyFoldersBuilder):
        config = client._build_folders_request_config()

    assert "displayName" in config.query_parameters.kwargs["select"]


def test_import_builder_finds_class() -> None:
    """_import_builder should return the class when found in a module."""
    module = ModuleType("fake_module")

    class Dummy:
        pass

    module.Dummy = Dummy

    with patch("src.email.client.import_module", return_value=module):
        result = EmailClient._import_builder(["fake_module"], "Dummy")

    assert result is Dummy


def test_import_builder_returns_none_when_missing() -> None:
    """_import_builder should return None when modules or classes are missing."""
    module = ModuleType("missing_module")

    with patch("src.email.client.import_module", side_effect=[ModuleNotFoundError("nope"), module]):
        result = EmailClient._import_builder(["nope", "missing_module"], "MissingClass")

    assert result is None


def test_extract_collection_variants() -> None:
    """_extract_collection should handle None, lists, and value attributes."""
    assert EmailClient._extract_collection(None) == []
    assert EmailClient._extract_collection([1, 2]) == [1, 2]

    response = MagicMock()
    response.value = [3]
    assert EmailClient._extract_collection(response) == [3]

    response = MagicMock()
    response.value = None
    assert EmailClient._extract_collection(response) == []
