"""Unit tests for CLI commands in src/cli/commands.py."""

from unittest.mock import AsyncMock, MagicMock, patch

from rich.panel import Panel

import src.cli.commands as commands


def make_settings(token_file: str = "token.json") -> MagicMock:
    """Create a fake settings object with a storage.token_file attribute."""
    storage = MagicMock()
    storage.token_file = token_file
    settings = MagicMock()
    settings.storage = storage
    settings.setup_logging = MagicMock()
    return settings


def test_status_not_authenticated() -> None:
    """When no valid token exists, status() should inform the user (no exception)."""
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = False

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
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
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.status()

        # Expect console.print called at least once to show authenticated status
        mock_console.print.assert_called()

        # Inspect the last call. console.print is passed a rich Panel object in normal execution.
        last_call = mock_console.print.call_args_list[-1][0]
        arg = last_call[0] if last_call else None
        if isinstance(arg, Panel):
            # Panel title is set to "Authentication Status" in the implementation
            assert arg.title == "Authentication Status" or "Authenticated" in str(arg.renderable)
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
