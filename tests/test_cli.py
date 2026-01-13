"""Tests for new CLI commands and helpers."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from rich.panel import Panel

import src.cli.commands as commands
from src.database.models import EmailModel


def make_settings() -> MagicMock:
    storage = MagicMock()
    storage.token_file = "/tmp/token.json"
    storage.attachments_dir = "/tmp/outmylook-attachments"
    database = MagicMock()
    database.url = "sqlite:///test.db"
    settings = MagicMock()
    settings.storage = storage
    settings.database = database
    settings.setup_logging = MagicMock()
    settings.ensure_directories = MagicMock()
    return settings


def make_email_model(email_id: str = "email-1") -> EmailModel:
    return EmailModel(
        id=email_id,
        subject="Subject",
        sender_email="alice@example.com",
        sender_name="Alice",
        received_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        body_preview="Preview",
        body_content=None,
        is_read=False,
        has_attachments=True,
        folder_id="inbox",
    )


@asynccontextmanager
async def fake_session_context():
    yield MagicMock()


def test_list_emails_uses_list_all() -> None:
    email = make_email_model()
    repo_instance = MagicMock()
    repo_instance.list_all = AsyncMock(return_value=[email])

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.EmailRepository", return_value=repo_instance),
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.list_emails()

        repo_instance.list_all.assert_awaited_once_with(limit=None, offset=0)
        mock_console.print.assert_called()


def test_list_emails_with_filters_calls_search() -> None:
    email = make_email_model()
    repo_instance = MagicMock()
    repo_instance.search = AsyncMock(return_value=[email])

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.EmailRepository", return_value=repo_instance),
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.list_emails(from_address="example.com", limit=1, offset=0)

        repo_instance.search.assert_awaited_once_with(
            sender="example.com",
            subject=None,
            date_from=None,
            date_to=None,
            is_read=None,
            has_attachments=None,
        )
        mock_console.print.assert_called()


def test_list_emails_empty_results() -> None:
    repo_instance = MagicMock()
    repo_instance.list_all = AsyncMock(return_value=[])

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.EmailRepository", return_value=repo_instance),
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.list_emails()

        mock_console.print.assert_called()


def test_list_emails_quiet_summary() -> None:
    email = make_email_model()
    repo_instance = MagicMock()
    repo_instance.list_all = AsyncMock(return_value=[email])

    commands._configure_output(verbose=False, quiet=True)
    try:
        with (
            patch("src.cli.commands.get_settings", return_value=make_settings()),
            patch("src.cli.commands.get_session", return_value=fake_session_context()),
            patch("src.cli.commands.EmailRepository", return_value=repo_instance),
            patch("src.cli.commands.console") as mock_console,
        ):
            commands.list_emails()

            mock_console.print.assert_called()
    finally:
        commands._configure_output(verbose=False, quiet=False)


def test_list_emails_error_exits() -> None:
    repo_instance = MagicMock()
    repo_instance.list_all = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.EmailRepository", return_value=repo_instance),
        patch("src.cli.commands.console"),
    ):
        with pytest.raises(typer.Exit):
            commands.list_emails()


def test_export_emails_calls_exporter(tmp_path: Path) -> None:
    email = make_email_model()
    repo_instance = MagicMock()
    repo_instance.list_all = AsyncMock(return_value=[email])

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.EmailRepository", return_value=repo_instance),
        patch("src.cli.commands.export_emails") as mock_export,
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.export(output_path=tmp_path / "emails.json", fmt="json")

        mock_export.assert_called_once()
        mock_console.print.assert_called()


def test_export_emails_with_filters_uses_search(tmp_path: Path) -> None:
    email = make_email_model()
    repo_instance = MagicMock()
    repo_instance.search = AsyncMock(return_value=[email])

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.EmailRepository", return_value=repo_instance),
        patch("src.cli.commands.export_emails") as mock_export,
        patch("src.cli.commands.console"),
    ):
        commands.export(output_path=tmp_path / "emails.json", fmt="json", from_address="example.com")

        repo_instance.search.assert_awaited_once()
        mock_export.assert_called_once()


def test_export_invalid_format_raises() -> None:
    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.console"),
    ):
        with pytest.raises(typer.BadParameter):
            commands.export(output_path=Path("out.txt"), fmt="yaml")


def test_export_emails_error_exits(tmp_path: Path) -> None:
    repo_instance = MagicMock()
    repo_instance.list_all = AsyncMock(return_value=[])

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands.EmailRepository", return_value=repo_instance),
        patch("src.cli.commands.export_emails", side_effect=RuntimeError("boom")),
        patch("src.cli.commands.console"),
    ):
        with pytest.raises(typer.Exit):
            commands.export(output_path=tmp_path / "emails.json", fmt="json")


def test_status_renders_panel() -> None:
    mock_token_cache = MagicMock()
    mock_token_cache.has_valid_token.return_value = True
    mock_token_cache.get_token_info = AsyncMock(
        return_value={"expires_at": "2026-01-01T00:00:00+00:00", "scopes": ["Mail.Read"]}
    )
    mock_token_cache.is_token_expiring_soon.return_value = False

    with (
        patch("src.cli.commands.get_settings", return_value=make_settings()),
        patch("src.cli.commands.TokenCache", return_value=mock_token_cache),
        patch("src.cli.commands.get_session", return_value=fake_session_context()),
        patch("src.cli.commands._get_email_count", new=AsyncMock(return_value=2)),
        patch("src.cli.commands.console") as mock_console,
    ):
        commands.status()

        last_call = mock_console.print.call_args_list[-1][0]
        arg = last_call[0] if last_call else None
        assert isinstance(arg, Panel)
        assert arg.title == "Status"


def test_main_callback_sets_output() -> None:
    commands.main_callback(verbose=True, quiet=False)
    assert commands._OUTPUT.verbose is True
    assert commands._OUTPUT.quiet is False
    commands._configure_output(verbose=False, quiet=False)


def test_configure_output_rejects_both() -> None:
    with pytest.raises(typer.BadParameter):
        commands._configure_output(verbose=True, quiet=True)


def test_setup_logging_respects_output() -> None:
    settings = make_settings()
    root_logger = commands.logging.getLogger()
    previous_level = root_logger.level
    try:
        commands._configure_output(verbose=True, quiet=False)
        commands._setup_logging(settings)
        assert root_logger.level == commands.logging.DEBUG

        commands._configure_output(verbose=False, quiet=True)
        commands._setup_logging(settings)
        assert root_logger.level == commands.logging.ERROR
    finally:
        commands._configure_output(verbose=False, quiet=False)
        root_logger.setLevel(previous_level)


def test_console_print_respects_quiet() -> None:
    commands._configure_output(verbose=False, quiet=True)
    try:
        with patch("src.cli.commands.console") as mock_console:
            commands._console_print("message")
            mock_console.print.assert_not_called()
            commands._console_print("error", level="error")
            mock_console.print.assert_called_once()
    finally:
        commands._configure_output(verbose=False, quiet=False)


def test_build_local_filters_rejects_conflicting_read() -> None:
    with pytest.raises(typer.BadParameter, match="Choose only one of --read or --unread"):
        commands._build_local_filters(
            from_address=None,
            subject=None,
            after=None,
            before=None,
            unread=True,
            read=True,
            has_attachments=False,
        )


def test_build_local_filters_rejects_after_after_before() -> None:
    with pytest.raises(typer.BadParameter, match="--after must be before or equal to --before"):
        commands._build_local_filters(
            from_address=None,
            subject=None,
            after="2024-02-01",
            before="2024-01-01",
            unread=False,
            read=False,
            has_attachments=False,
        )


def test_normalize_text_filter_rejects_empty() -> None:
    with pytest.raises(typer.BadParameter, match="Sender filter cannot be empty"):
        commands._normalize_text_filter(" ", "Sender")


def test_resolve_read_value_variants() -> None:
    assert commands._resolve_read_value(read=True, unread=False) is True
    assert commands._resolve_read_value(read=False, unread=True) is False
    assert commands._resolve_read_value(read=False, unread=False) is None


def test_apply_offset_limit_slices() -> None:
    emails = [make_email_model("a"), make_email_model("b"), make_email_model("c")]
    result = commands._apply_offset_limit(emails, limit=1, offset=1)
    assert [email.id for email in result] == ["b"]


@pytest.mark.asyncio
async def test_get_email_count_returns_value() -> None:
    result = MagicMock()
    result.scalar.return_value = 5
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    assert await commands._get_email_count(session) == 5


def test_format_database_label_non_sqlite() -> None:
    label = commands._format_database_label("postgresql://localhost/db", 10)
    assert "postgresql://localhost/db" in label
    assert "10 emails" in label


def test_get_attachment_stats_counts_files(tmp_path: Path) -> None:
    file_one = tmp_path / "one.txt"
    file_one.write_text("a")
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    file_two = nested_dir / "two.txt"
    file_two.write_text("bb")

    count, size = commands._get_attachment_stats(tmp_path)

    assert count == 2
    assert size == 3


def test_parse_date_input_accepts_date_only() -> None:
    parsed = commands._parse_date_input("2024-01-01", "after")
    assert parsed.year == 2024
