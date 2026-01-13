"""Unit tests for CLI commands in src/cli/commands.py."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
import typer
from rich.panel import Panel

import src.cli.commands as commands
from src.auth import AuthenticationError
from src.email.models import Email, EmailAddress


def make_settings(token_file: str = "token.json") -> MagicMock:
    """Create a fake settings object with a storage.token_file attribute."""
    storage = MagicMock()
    storage.token_file = token_file
    storage.attachments_dir = "/tmp/outmylook-attachments"
    database = MagicMock()
    database.url = "sqlite:///test.db"
    settings = MagicMock()
    settings.storage = storage
    settings.database = database
    settings.setup_logging = MagicMock()
    settings.ensure_directories = MagicMock()
    return settings


@asynccontextmanager
async def fake_session_context():
    yield MagicMock()


def test_status_not_authenticated() -> None:
    """When no valid token exists, status() should inform the user (no exception)."""
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = False

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands._get_email_count", new=AsyncMock(return_value=0)),
        patch("src.cli.commands.console") as mock_console,
    ):
        # Call the command which uses asyncio.run internally
        commands.status()

        # console.print should have been called to show "Not authenticated" message
        mock_console.print.assert_called()


def test_status_authenticated_shows_token_info() -> None:
    """When a valid token exists, status() should display token info."""
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = True
    mock_token_cache.get_token_info = AsyncMock(
        return_value={
            "expires_at": "2026-01-01T00:00:00+00:00",
            "seconds_until_expiry": 3600,
            "scopes": ["Mail.Read"],
            "cached_at": "2026-01-01T00:00:00+00:00",
        }
    )
    mock_token_cache.is_token_expiring_soon.return_value = False

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands._get_email_count", new=AsyncMock(return_value=0)),
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.status()

        # Expect console.print called at least once to show authenticated status
        mock_console.print.assert_called()

        # Inspect the last call. console.print is passed a rich Panel object in normal execution.
        last_call = mock_console.print.call_args_list[-1][0]
        arg = last_call[0] if last_call else None
        if isinstance(arg, Panel):
            assert arg.title == "Status" or "Authenticated" in str(arg.renderable)
        else:
            # join string representations of arguments to check content
            joined = " ".join(str(a) for a in last_call)
            assert "Authenticated" in joined or "Authentication Status" in joined


def test_logout_no_active_session() -> None:
    """Logout should inform when there is no active session and not raise."""
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = False

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.logout()

        mock_console.print.assert_called()


def test_logout_clears_token_when_present() -> None:
    """When a token exists logout() should clear it and report success."""
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = True
    mock_token_cache.clear = AsyncMock()

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.logout()

        # clear() should have been awaited
        mock_token_cache.clear.assert_awaited()

        # console.print should report successful logout
        mock_console.print.assert_called()


def test_login_already_authenticated_no_reauth() -> None:
    """If already authenticated and user declines re-auth, login() returns early."""
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = True
    mock_token_cache.get_token_info = AsyncMock(
        return_value={"expires_at": "2026-01-01T00:00:00+00:00", "scopes": ["Mail.Read"]}
    )

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.typer.confirm", return_value=False),
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.login()
        # token_cache.clear should not be called since re-auth was declined
        assert not getattr(mock_token_cache, "clear", MagicMock()).called
        mock_console.print.assert_called()


def test_login_already_authenticated_reauth_and_success() -> None:
    """If user opts to re-authenticate, token is cleared and auth proceeds successfully."""
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = True
    mock_token_cache.get_token_info = AsyncMock(
        return_value={"expires_at": "2026-01-01T00:00:00+00:00", "scopes": ["Mail.Read"]}
    )
    mock_token_cache.clear = AsyncMock()

    # Fake authenticator that returns a fake client with user info
    fake_client = MagicMock()
    fake_user = MagicMock()
    fake_user.display_name = "Test User"
    fake_user.user_principal_name = "test@example.com"
    fake_client.me.get = AsyncMock(return_value=fake_user)

    fake_authenticator = MagicMock()
    fake_authenticator.authenticate = AsyncMock(return_value=fake_client)

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.typer.confirm", return_value=True),
        patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
        patch("src.cli.commands.console") as mock_console,
    ):
        mock_graph_auth.from_settings.return_value = fake_authenticator
        commands.login()

        mock_token_cache.clear.assert_awaited()
        mock_console.print.assert_called()


def test_login_authentication_error_exits() -> None:
    """If authenticator raises AuthenticationError, login exits with an error."""
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = False

    fake_authenticator = MagicMock()
    fake_authenticator.authenticate = AsyncMock(side_effect=AuthenticationError("bad auth"))

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.console") as mock_console,
    ):
        mock_graph_auth.from_settings.return_value = fake_authenticator
        with pytest.raises(typer.Exit):
            commands.login()
        mock_console.print.assert_called()


def test_login_unexpected_error_exits() -> None:
    """If get_settings raises, login should handle and exit."""
    with (
        patch("src.cli.commands.get_settings", side_effect=Exception("boom")),
        patch("src.cli.commands.console") as mock_console,
    ):
        with pytest.raises(typer.Exit):
            commands.login()
        mock_console.print.assert_called()


def test_status_token_info_unavailable() -> None:
    """When token exists but token info is None, should print 'Token information unavailable'."""
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = True
    mock_token_cache.get_token_info = AsyncMock(return_value=None)

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands._get_email_count", new=AsyncMock(return_value=0)),
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.status()
        last_call = mock_console.print.call_args_list[-1][0]
        arg = last_call[0] if last_call else None
        assert getattr(arg, "title", None) == "Status"


def test_status_expiring_soon_shows_note() -> None:
    """When token is expiring soon, status should include a note about refresh."""
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = True
    mock_token_cache.get_token_info = AsyncMock(
        return_value={
            "expires_at": "2026-01-01T00:00:00+00:00",
            "seconds_until_expiry": 10,
            "scopes": ["Mail.Read"],
            "cached_at": "2026-01-01T00:00:00+00:00",
        }
    )
    mock_token_cache.is_token_expiring_soon.return_value = True

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands._get_email_count", new=AsyncMock(return_value=0)),
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.status()
        # The note about token refresh is printed after the main panel
        assert mock_console.print.call_count >= 2


def test_logout_clear_raises_exit() -> None:
    """If clearing token fails during logout, logout should exit with an error."""
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = True
    mock_token_cache.clear = AsyncMock(side_effect=Exception("boom"))

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.console") as mock_console,
    ):
        with pytest.raises(typer.Exit):
            commands.logout()
        mock_console.print.assert_called()


def test_main_calls_app() -> None:
    """main() should call the Typer app."""
    with patch("src.cli.commands.app") as mock_app:
        commands.main()
        mock_app.assert_called_once()


def test_status_unexpected_error_exits() -> None:
    """If get_settings raises in status, it should handle and exit."""
    with (
        patch("src.cli.commands.get_settings", side_effect=Exception("boom")),
        patch("src.cli.commands.console") as mock_console,
    ):
        with pytest.raises(typer.Exit):
            commands.status()
        mock_console.print.assert_called()


def test_fetch_requires_authentication() -> None:
    """Fetch should exit when not authenticated."""
    mock_token_cache = MagicMock()

    fake_authenticator = MagicMock()
    fake_authenticator.get_client = AsyncMock(side_effect=AuthenticationError("auth failed"))

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
        patch("src.cli.commands.console") as mock_console,
    ):
        mock_graph_auth.from_settings.return_value = fake_authenticator
        with pytest.raises(typer.Exit):
            commands.fetch()
        mock_console.print.assert_called()


def test_fetch_success_renders_table() -> None:
    """Fetch should render a table when emails are returned."""
    mock_token_cache = MagicMock()

    fake_client = MagicMock()
    fake_authenticator = MagicMock()
    fake_authenticator.get_client = AsyncMock(return_value=fake_client)

    email = Email(
        id="msg-1",
        subject="Subject",
        sender=EmailAddress(address="alice@example.com", name="Alice"),
        received_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        body_preview="Preview",
        body_content=None,
        is_read=False,
        has_attachments=False,
        folder_id="inbox",
    )

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
        patch("src.cli.commands.EmailClient", autospec=True) as mock_email_client,
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.console") as mock_console,
    ):
        mock_graph_auth.from_settings.return_value = fake_authenticator
        mock_email_client_instance = MagicMock()
        mock_email_client_instance.list_emails = AsyncMock(return_value=[email])
        mock_email_client.return_value = mock_email_client_instance

        commands.fetch(limit=1, folder="inbox", skip=0)

        mock_email_client.assert_called_with(fake_client, email_repository=ANY)
        mock_email_client_instance.list_emails.assert_awaited_with(folder="inbox", limit=1, skip=0, email_filter=None)
        mock_console.print.assert_called()


def test_fetch_quiet_summary() -> None:
    """Fetch should print a summary in quiet mode."""
    mock_token_cache = MagicMock()

    fake_client = MagicMock()
    fake_authenticator = MagicMock()
    fake_authenticator.get_client = AsyncMock(return_value=fake_client)

    email = Email(
        id="msg-1",
        subject="Subject",
        sender=EmailAddress(address="alice@example.com", name="Alice"),
        received_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        body_preview="Preview",
        body_content=None,
        is_read=False,
        has_attachments=False,
        folder_id="inbox",
    )

    commands._configure_output(verbose=False, quiet=True)
    try:
        with (
            patch("src.cli.commands.get_settings", return_value=make_settings()),
            patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
            patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
            patch("src.cli.commands.EmailClient", autospec=True) as mock_email_client,
            patch("src.cli.commands.get_session", return_value=fake_session_context()),
            patch("src.cli.commands.console") as mock_console,
            patch("src.cli.commands.build_email_table") as mock_table,
        ):
            mock_graph_auth.from_settings.return_value = fake_authenticator
            mock_email_client_instance = MagicMock()
            mock_email_client_instance.list_emails = AsyncMock(return_value=[email])
            mock_email_client.return_value = mock_email_client_instance

            commands.fetch(limit=1, folder="inbox", skip=0)

            mock_table.assert_not_called()
            mock_console.print.assert_called()
    finally:
        commands._configure_output(verbose=False, quiet=False)


def test_fetch_unexpected_error_exits() -> None:
    """Fetch should exit on unexpected errors."""
    mock_token_cache = MagicMock()

    fake_client = MagicMock()
    fake_authenticator = MagicMock()
    fake_authenticator.get_client = AsyncMock(return_value=fake_client)

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
        patch("src.cli.commands.EmailClient", autospec=True) as mock_email_client,
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.console"),
    ):
        mock_graph_auth.from_settings.return_value = fake_authenticator
        mock_email_client_instance = MagicMock()
        mock_email_client_instance.list_emails = AsyncMock(side_effect=RuntimeError("boom"))
        mock_email_client.return_value = mock_email_client_instance

        with pytest.raises(typer.Exit):
            commands.fetch(limit=1, folder="inbox", skip=0)


def test_fetch_empty_folder() -> None:
    """Fetch should handle empty folders gracefully."""
    mock_token_cache = MagicMock()

    fake_client = MagicMock()
    fake_authenticator = MagicMock()
    fake_authenticator.get_client = AsyncMock(return_value=fake_client)

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
        patch("src.cli.commands.EmailClient", autospec=True) as mock_email_client,
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.console") as mock_console,
    ):
        mock_graph_auth.from_settings.return_value = fake_authenticator
        mock_email_client_instance = MagicMock()
        mock_email_client_instance.list_emails = AsyncMock(return_value=[])
        mock_email_client.return_value = mock_email_client_instance

        commands.fetch(limit=5, folder="inbox", skip=0)

        mock_email_client.assert_called_with(fake_client, email_repository=ANY)
        mock_email_client_instance.list_emails.assert_awaited_with(folder="inbox", limit=5, skip=0, email_filter=None)
        mock_console.print.assert_called()


def test_download_requires_email_or_filters() -> None:
    """download should require an email ID or filters."""
    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.console") as mock_console,
    ):
        with pytest.raises(typer.BadParameter):
            commands.download()
        mock_console.print.assert_not_called()


def test_download_attachment_requires_email_id() -> None:
    """download should require email_id when --attachment is provided."""
    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.console") as mock_console,
    ):
        with pytest.raises(typer.BadParameter):
            commands.download(attachment_id="att-1")
        mock_console.print.assert_not_called()


def test_download_specific_attachment() -> None:
    """download should call AttachmentHandler for a specific attachment."""
    mock_token_cache = MagicMock()

    fake_client = MagicMock()
    fake_authenticator = MagicMock()
    fake_authenticator.get_client = AsyncMock(return_value=fake_client)

    handler_instance = MagicMock()
    handler_instance.download_attachment = AsyncMock(return_value="/tmp/file.txt")

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
        patch("src.cli.commands.EmailRepository", autospec=True),
        patch("src.cli.commands.AttachmentRepository", autospec=True),
        patch("src.cli.commands.AttachmentHandler", return_value=handler_instance) as mock_handler,
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.console") as mock_console,
    ):
        mock_graph_auth.from_settings.return_value = fake_authenticator

        commands.download(email_id="email-1", attachment_id="att-1")

        mock_handler.assert_called_once()
        handler_instance.download_attachment.assert_awaited_once_with("email-1", "att-1")
        mock_console.print.assert_called()


def test_download_authentication_error_exits() -> None:
    """download should exit on authentication errors."""
    mock_token_cache = MagicMock()

    fake_authenticator = MagicMock()
    fake_authenticator.get_client = AsyncMock(side_effect=AuthenticationError("auth failed"))

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
        patch("src.cli.commands.console"),
    ):
        mock_graph_auth.from_settings.return_value = fake_authenticator

        with pytest.raises(typer.Exit):
            commands.download(email_id="email-1")


def test_download_no_attachments() -> None:
    """download should report when no attachments are found for an email."""
    mock_token_cache = MagicMock()

    fake_client = MagicMock()
    fake_authenticator = MagicMock()
    fake_authenticator.get_client = AsyncMock(return_value=fake_client)

    handler_instance = MagicMock()
    handler_instance.download_all_for_email = AsyncMock(return_value=[])

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
        patch("src.cli.commands.EmailRepository", autospec=True),
        patch("src.cli.commands.AttachmentRepository", autospec=True),
        patch("src.cli.commands.AttachmentHandler", return_value=handler_instance),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.console") as mock_console,
    ):
        mock_graph_auth.from_settings.return_value = fake_authenticator

        commands.download(email_id="email-1")

        handler_instance.download_all_for_email.assert_awaited_once_with("email-1")
        mock_console.print.assert_called()


def test_download_filters_unread_with_attachments() -> None:
    """download should call download_all_for_email for filtered emails."""
    mock_token_cache = MagicMock()

    fake_client = MagicMock()
    fake_authenticator = MagicMock()
    fake_authenticator.get_client = AsyncMock(return_value=fake_client)

    email_one = MagicMock()
    email_one.id = "email-1"
    email_two = MagicMock()
    email_two.id = "email-2"

    email_repo_instance = MagicMock()
    email_repo_instance.search = AsyncMock(return_value=[email_one, email_two])

    handler_instance = MagicMock()
    handler_instance.download_all_for_email = AsyncMock(return_value=[])

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
        patch("src.cli.commands.EmailRepository", return_value=email_repo_instance),
        patch("src.cli.commands.AttachmentRepository", autospec=True),
        patch("src.cli.commands.AttachmentHandler", return_value=handler_instance),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.console") as mock_console,
    ):
        mock_graph_auth.from_settings.return_value = fake_authenticator

        commands.download(unread=True, has_attachments=True)

        email_repo_instance.search.assert_awaited_once_with(is_read=False, has_attachments=True)
        handler_instance.download_all_for_email.assert_any_await("email-1")
        handler_instance.download_all_for_email.assert_any_await("email-2")
        mock_console.print.assert_called()


def test_download_filters_no_matches() -> None:
    """download should report when no emails match filters."""
    mock_token_cache = MagicMock()

    fake_client = MagicMock()
    fake_authenticator = MagicMock()
    fake_authenticator.get_client = AsyncMock(return_value=fake_client)

    email_repo_instance = MagicMock()
    email_repo_instance.search = AsyncMock(return_value=[])

    handler_instance = MagicMock()
    handler_instance.download_all_for_email = AsyncMock(return_value=[])

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.GraphAuthenticator", autospec=True) as mock_graph_auth,
        patch("src.cli.commands.EmailRepository", return_value=email_repo_instance),
        patch("src.cli.commands.AttachmentRepository", autospec=True),
        patch("src.cli.commands.AttachmentHandler", return_value=handler_instance),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.console") as mock_console,
    ):
        mock_graph_auth.from_settings.return_value = fake_authenticator

        commands.download(unread=True, has_attachments=True)

        email_repo_instance.search.assert_awaited_once_with(is_read=False, has_attachments=True)
        handler_instance.download_all_for_email.assert_not_called()
        mock_console.print.assert_called()


def test_build_email_filter_returns_none_when_no_filters() -> None:
    """_build_email_filter should return None when no filters are provided."""
    result = commands._build_email_filter(
        from_address=None,
        subject=None,
        after=None,
        before=None,
        unread=False,
        read=False,
        has_attachments=False,
    )
    assert result is None


def test_build_email_filter_combines_filters() -> None:
    """_build_email_filter should combine multiple filters."""
    result = commands._build_email_filter(
        from_address="boss@company.com",
        subject="invoice",
        after="2024-01-01",
        before="2024-01-31",
        unread=True,
        read=False,
        has_attachments=True,
    )
    assert result is not None
    assert result.build() == (
        "from/emailAddress/address eq 'boss@company.com' and contains(subject, 'invoice') "
        "and receivedDateTime ge 2024-01-01T00:00:00Z and receivedDateTime le 2024-01-31T00:00:00Z "
        "and isRead eq false and hasAttachments eq true"
    )


def test_build_email_filter_rejects_read_and_unread() -> None:
    """_build_email_filter should reject conflicting read flags."""
    with pytest.raises(typer.BadParameter, match="Choose only one of --read or --unread"):
        commands._build_email_filter(
            from_address=None,
            subject=None,
            after=None,
            before=None,
            unread=True,
            read=True,
            has_attachments=False,
        )


def test_build_email_filter_rejects_bad_date() -> None:
    """_build_email_filter should error on invalid date inputs."""
    with pytest.raises(typer.BadParameter, match="Invalid after date"):
        commands._build_email_filter(
            from_address=None,
            subject=None,
            after="not-a-date",
            before=None,
            unread=False,
            read=False,
            has_attachments=False,
        )


def test_build_email_filter_rejects_empty_from() -> None:
    """_build_email_filter should error on empty sender values."""
    with pytest.raises(typer.BadParameter, match="Sender address cannot be empty"):
        commands._build_email_filter(
            from_address="   ",
            subject=None,
            after=None,
            before=None,
            unread=False,
            read=False,
            has_attachments=False,
        )


def test_build_email_filter_rejects_empty_subject() -> None:
    """_build_email_filter should error on empty subject values."""
    with pytest.raises(typer.BadParameter, match="Subject filter text cannot be empty"):
        commands._build_email_filter(
            from_address=None,
            subject=" ",
            after=None,
            before=None,
            unread=False,
            read=False,
            has_attachments=False,
        )


def test_build_email_filter_read_true() -> None:
    """_build_email_filter should set read filter when requested."""
    result = commands._build_email_filter(
        from_address=None,
        subject=None,
        after=None,
        before=None,
        unread=False,
        read=True,
        has_attachments=False,
    )
    assert result is not None
    assert result.build() == "isRead eq true"


def test_build_email_filter_rejects_after_after_before() -> None:
    """_build_email_filter should error when after is after before."""
    with pytest.raises(typer.BadParameter, match="--after must be before or equal to --before"):
        commands._build_email_filter(
            from_address=None,
            subject=None,
            after="2024-02-01",
            before="2024-01-01",
            unread=False,
            read=False,
            has_attachments=False,
        )


def test_parse_date_input_accepts_zulu() -> None:
    """_parse_date_input should parse Zulu timestamps."""
    parsed = commands._parse_date_input("2024-01-01T10:00:00Z", "after")
    assert parsed.tzinfo is not None


def test_parse_date_input_rejects_empty() -> None:
    """_parse_date_input should reject empty date input."""
    with pytest.raises(typer.BadParameter, match="after date cannot be empty"):
        commands._parse_date_input("  ", "after")
