"""CLI commands for OutMyLook."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any, Callable, Iterable, Optional, TypedDict

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.attachments import AttachmentHandler
from src.auth import AuthenticationError, GraphAuthenticator, TokenCache
from src.cli.exporters import SUPPORTED_FORMATS, export_emails
from src.cli.formatters import build_email_table, build_status_panel, format_bytes
from src.config.settings import Settings, get_settings
from src.database.models import EmailModel
from src.database.repository import AttachmentRepository, EmailRepository, get_session
from src.email import EmailClient, EmailFilter

app = typer.Typer(help="OutMyLook - Microsoft Outlook email management tool")
console = Console()
logger = logging.getLogger(__name__)

NOMINA_SENDER_DEFAULT = "noreply.laboral.bcn@bdo.es"
NOMINA_SUBJECT_DEFAULT = "Hojas de Salario"
NOMINA_BATCH_SIZE = 100


@dataclass
class OutputOptions:
    """Track global output flags for the CLI."""

    verbose: bool = False
    quiet: bool = False


_OUTPUT = OutputOptions()


class EmailSearchFilters(TypedDict):
    """Typed dictionary for local email search filters."""

    sender: Optional[str]
    subject: Optional[str]
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    is_read: Optional[bool]
    has_attachments: Optional[bool]


@app.callback()
def main_callback(
    verbose: Annotated[bool, typer.Option("--verbose", help="Show verbose output")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", help="Suppress non-essential output")] = False,
) -> None:
    """Configure global CLI output."""
    _configure_output(verbose, quiet)


def _configure_output(verbose: bool, quiet: bool) -> None:
    if verbose and quiet:
        raise typer.BadParameter("Choose only one of --verbose or --quiet.")
    _OUTPUT.verbose = verbose
    _OUTPUT.quiet = quiet


def _setup_logging(settings: Settings) -> None:
    settings.setup_logging()
    root_logger = logging.getLogger()
    if _OUTPUT.verbose:
        root_logger.setLevel(logging.DEBUG)
    if _OUTPUT.quiet:
        root_logger.setLevel(logging.ERROR)


def _console_print(*args, level: str = "info") -> None:
    if _OUTPUT.quiet and level not in {"error", "summary"}:
        return
    console.print(*args)


def _render_error(action: str, message: str, exc: Exception) -> None:
    logger.exception("%s failed", action)
    _console_print(
        Panel.fit(
            f"✗ {message}\n\n{str(exc)}",
            title="Error",
            border_style="red",
        ),
        level="error",
    )


@app.command()
def login(
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to configuration file"),
) -> None:
    """Authenticate with Microsoft Graph using Device Code Flow.

    This command will guide you through the authentication process:
    1. Display a URL and code
    2. Open the URL in your browser
    3. Enter the code when prompted
    4. Grant permissions to the application
    5. Token will be cached for future use
    """
    asyncio.run(_login_async(config_file))


async def _login_async(config_file: Optional[str]) -> None:
    """Async implementation of login command.

    Args:
        config_file: Optional path to configuration file
    """
    try:
        # Load settings
        settings = get_settings()
        _setup_logging(settings)

        # Check if already authenticated
        token_cache = TokenCache(settings.storage.token_file)

        if token_cache.has_valid_token():
            token_info = await token_cache.get_token_info()
            if token_info:
                _console_print(
                    Panel.fit(
                        f"✓ Already authenticated!\n\n"
                        f"Token expires: {token_info['expires_at']}\n"
                        f"Scopes: {', '.join(token_info['scopes'])}",
                        title="Authentication Status",
                        border_style="green",
                    )
                )

            if not typer.confirm("Do you want to re-authenticate?", default=False):
                return

            # Clear existing token
            await token_cache.clear()
            _console_print("[yellow]Cleared existing token[/yellow]\n")

        # Create authenticator
        authenticator = GraphAuthenticator.from_settings(settings.azure, token_cache=token_cache)

        # Display authentication instructions
        _console_print(
            Panel.fit(
                "You will be prompted to:\n"
                "1. Visit a URL in your browser\n"
                "2. Enter the device code shown\n"
                "3. Sign in with your Microsoft account\n"
                "4. Grant permissions to OutMyLook",
                title="Authentication Flow",
                border_style="blue",
            )
        )

        # Perform authentication
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Authenticating...", total=None)

            try:
                client = await authenticator.authenticate()

                # Get user info to confirm
                user = await client.me.get()

                _console_print()
                display_name = user.display_name if user else "Unknown"
                email = user.user_principal_name if user else "Unknown"
                _console_print(
                    Panel.fit(
                        f"✓ Authentication successful!\n\n"
                        f"Logged in as: {display_name}\n"
                        f"Email: {email}\n\n"
                        f"Token cached to: {settings.storage.token_file}",
                        title="Success",
                        border_style="green",
                    ),
                    level="summary",
                )

            except AuthenticationError as e:
                _console_print(
                    Panel.fit(
                        f"✗ Authentication failed\n\n{str(e)}",
                        title="Error",
                        border_style="red",
                    ),
                    level="error",
                )
                raise typer.Exit(code=1)

    except Exception as e:
        _render_error("Login", "Unexpected error during login", e)
        raise typer.Exit(code=1)


@app.command()
def logout() -> None:
    """Logout and clear cached authentication tokens."""
    asyncio.run(_logout_async())


async def _logout_async() -> None:
    """Async implementation of logout command."""
    try:
        settings = get_settings()
        _setup_logging(settings)
        settings.ensure_directories()
        logger.debug("Starting logout")
        token_cache = TokenCache(settings.storage.token_file)
        auth_record_path = Path(settings.storage.token_file).expanduser().parent / "auth_record.json"
        has_session = token_cache.has_valid_token() or auth_record_path.exists()

        if not has_session:
            _console_print(
                Panel.fit(
                    "No active session found. You are not logged in.",
                    title="Logout",
                    border_style="yellow",
                ),
                level="summary",
            )
            return

        authenticator = GraphAuthenticator.from_settings(settings.azure, token_cache=token_cache)
        await authenticator.logout()

        _console_print(
            Panel.fit(
                "✓ Successfully logged out\n\nYour authentication data has been removed.",
                title="Logout",
                border_style="green",
            ),
            level="summary",
        )

    except Exception as e:
        _render_error("Logout", "Error during logout", e)
        raise typer.Exit(code=1)


@app.command()
def status() -> None:
    """Check authentication status and token information."""
    asyncio.run(_status_async())


async def _status_async() -> None:
    """Async implementation of status command."""
    try:
        settings = get_settings()
        _setup_logging(settings)
        settings.ensure_directories()
        token_cache = TokenCache(settings.storage.token_file)

        auth_lines: list[tuple[str, str]] = []
        token_info = None
        if token_cache.has_valid_token():
            token_info = await token_cache.get_token_info()
            user_hint = None if token_info is None else token_info.get("user_principal_name")
            auth_value = f"✓ Logged in as {user_hint}" if user_hint else "✓ Authenticated"
            auth_lines.append(("Authentication", auth_value))
            if token_info:
                auth_lines.append(("Token expires", str(token_info.get("expires_at", "Unknown"))))
        else:
            auth_lines.append(("Authentication", "✗ Not authenticated"))

        async with get_session(settings.database.url) as session:
            email_count = await _get_email_count(session)

        db_label = _format_database_label(settings.database.url, email_count)
        attachments_count, attachments_bytes = _get_attachment_stats(Path(settings.storage.attachments_dir))
        attachments_label = (
            f"{Path(settings.storage.attachments_dir).expanduser()} "
            f"({attachments_count} files, {format_bytes(attachments_bytes)})"
        )

        status_panel = build_status_panel(
            [
                *auth_lines,
                ("Database", db_label),
                ("Attachments", attachments_label),
            ],
            title="Status",
        )
        _console_print(status_panel, level="summary")

        if token_info and token_cache.is_token_expiring_soon():
            _console_print("[yellow]Note: Token is expiring soon. It will be refreshed automatically on next use.[/yellow]")

    except Exception as e:
        _render_error("Status", "Error checking status", e)
        raise typer.Exit(code=1)


@app.command()
def fetch(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of emails to fetch")] = 25,
    folder: Annotated[str, typer.Option("--folder", "-f", help="Mail folder to fetch from")] = "inbox",
    skip: Annotated[int, typer.Option("--skip", help="Number of emails to skip")] = 0,
    from_address: Annotated[Optional[str], typer.Option("--from", help="Filter by sender email address")] = None,
    subject: Annotated[Optional[str], typer.Option("--subject", help="Filter by subject containing text")] = None,
    after: Annotated[Optional[str], typer.Option("--after", help="Filter by received date (YYYY-MM-DD or ISO-8601)")] = None,
    before: Annotated[Optional[str], typer.Option("--before", help="Filter by received date (YYYY-MM-DD or ISO-8601)")] = None,
    unread: Annotated[bool, typer.Option("--unread", help="Filter to unread emails only")] = False,
    read: Annotated[bool, typer.Option("--read", help="Filter to read emails only")] = False,
    has_attachments: Annotated[bool, typer.Option("--has-attachments", help="Filter to emails with attachments")] = False,
    ids: Annotated[bool, typer.Option("--ids", help="Print copy-friendly email IDs")] = False,
) -> None:
    """Fetch emails from Microsoft Graph."""
    email_filter = _build_email_filter(
        from_address=from_address,
        subject=subject,
        after=after,
        before=before,
        unread=unread,
        read=read,
        has_attachments=has_attachments,
    )
    asyncio.run(_fetch_async(folder, limit, skip, email_filter, ids))


async def _fetch_async(folder: str, limit: int, skip: int, email_filter: Optional[EmailFilter], show_ids: bool) -> None:
    """Async implementation of fetch command."""
    try:
        settings = get_settings()
        _setup_logging(settings)
        settings.ensure_directories()
        logger.debug(
            "Starting fetch: folder=%s limit=%s skip=%s filter=%s",
            folder,
            limit,
            skip,
            email_filter,
        )

        token_cache = TokenCache(settings.storage.token_file)
        authenticator = GraphAuthenticator.from_settings(settings.azure, token_cache=token_cache)
        graph_client = await authenticator.get_client()

        async with get_session(settings.database.url) as session:
            repository = EmailRepository(session)
            email_client = EmailClient(graph_client, email_repository=repository)
            emails = await email_client.list_emails(folder=folder, limit=limit, skip=skip, email_filter=email_filter)

        if not emails:
            _console_print(
                Panel.fit(
                    f"No emails found in '{folder}'.",
                    title="Fetch",
                    border_style="yellow",
                ),
                level="summary",
            )
            return

        if _OUTPUT.quiet:
            _console_print(
                Panel.fit(
                    f"✓ Fetched {len(emails)} email(s) from '{folder}'.",
                    title="Fetch",
                    border_style="green",
                ),
                level="summary",
            )
            return

        table = build_email_table(emails, title=f"Emails in {folder}", include_id=show_ids, include_read=True)
        _console_print(table)
        if show_ids:
            _emit_email_ids(emails)

    except AuthenticationError as e:
        _console_print(
            Panel.fit(
                f"Authentication failed\n\n{str(e)}\n\nRun 'outmylook login' to authenticate.",
                title="Authentication Required",
                border_style="red",
            ),
            level="error",
        )
        raise typer.Exit(code=1)
    except Exception as e:
        _render_error("Fetch", "Error fetching emails", e)
        raise typer.Exit(code=1)


@app.command()
def download(
    email_id: Annotated[Optional[str], typer.Argument(help="Email ID to download attachments from")] = None,
    attachment_id: Annotated[
        Optional[str], typer.Option("--attachment", "-a", help="Specific attachment ID to download")
    ] = None,
    unread: Annotated[bool, typer.Option("--unread", help="Download attachments for unread emails")] = False,
    has_attachments: Annotated[
        bool, typer.Option("--has-attachments", help="Download attachments for emails with attachments")
    ] = False,
) -> None:
    """Download attachments from Microsoft Graph."""
    asyncio.run(_download_async(email_id, attachment_id, unread, has_attachments))


@app.command("download-nomina")
def download_nomina(
    hours: Annotated[int, typer.Option("--hours", help="Look back this many hours")] = 24,
    folder: Annotated[str, typer.Option("--folder", "-f", help="Mail folder to scan")] = "inbox",
    sender: Annotated[str, typer.Option("--sender", help="Sender email address to match")] = NOMINA_SENDER_DEFAULT,
    subject: Annotated[str, typer.Option("--subject", help="Subject text to match")] = NOMINA_SUBJECT_DEFAULT,
) -> None:
    """Download payroll attachments from recent emails."""
    if hours <= 0:
        raise typer.BadParameter("--hours must be greater than 0.")
    sender_value = sender.strip()
    subject_value = subject.strip()
    if not sender_value and not subject_value:
        raise typer.BadParameter("Provide --sender and/or --subject.")
    asyncio.run(
        _download_nomina_async(
            hours,
            folder,
            sender_value or None,
            subject_value or None,
        )
    )


@app.command("list")
def list_emails(
    limit: Annotated[Optional[int], typer.Option("--limit", "-l", help="Max emails to list")] = None,
    offset: Annotated[int, typer.Option("--offset", help="Offset into stored emails")] = 0,
    from_address: Annotated[Optional[str], typer.Option("--from", help="Filter by sender email address")] = None,
    subject: Annotated[Optional[str], typer.Option("--subject", help="Filter by subject containing text")] = None,
    after: Annotated[Optional[str], typer.Option("--after", help="Filter by received date (YYYY-MM-DD or ISO-8601)")] = None,
    before: Annotated[Optional[str], typer.Option("--before", help="Filter by received date (YYYY-MM-DD or ISO-8601)")] = None,
    unread: Annotated[bool, typer.Option("--unread", help="Filter to unread emails only")] = False,
    read: Annotated[bool, typer.Option("--read", help="Filter to read emails only")] = False,
    has_attachments: Annotated[bool, typer.Option("--has-attachments", help="Filter to emails with attachments")] = False,
    ids: Annotated[bool, typer.Option("--ids", help="Print copy-friendly email IDs")] = False,
) -> None:
    """List stored emails from the local database."""
    asyncio.run(_list_async(limit, offset, from_address, subject, after, before, unread, read, has_attachments, ids))


@app.command()
def export(
    output_path: Annotated[Path, typer.Argument(help="Export file path")],
    fmt: Annotated[str, typer.Option("--format", "-f", help="Export format (json or csv)")] = "json",
    from_address: Annotated[Optional[str], typer.Option("--from", help="Filter by sender email address")] = None,
    subject: Annotated[Optional[str], typer.Option("--subject", help="Filter by subject containing text")] = None,
    after: Annotated[Optional[str], typer.Option("--after", help="Filter by received date (YYYY-MM-DD or ISO-8601)")] = None,
    before: Annotated[Optional[str], typer.Option("--before", help="Filter by received date (YYYY-MM-DD or ISO-8601)")] = None,
    unread: Annotated[bool, typer.Option("--unread", help="Filter to unread emails only")] = False,
    read: Annotated[bool, typer.Option("--read", help="Filter to read emails only")] = False,
    has_attachments: Annotated[bool, typer.Option("--has-attachments", help="Filter to emails with attachments")] = False,
) -> None:
    """Export stored emails to JSON or CSV."""
    asyncio.run(_export_async(output_path, fmt, from_address, subject, after, before, unread, read, has_attachments))


async def _download_async(
    email_id: Optional[str],
    attachment_id: Optional[str],
    unread: bool,
    has_attachments: bool,
) -> None:
    """Async implementation of download command."""
    try:
        settings = get_settings()
        _setup_logging(settings)
        settings.ensure_directories()
        email_id = _normalize_graph_id(email_id)
        attachment_id = _normalize_graph_id(attachment_id)
        logger.debug(
            "Starting download: email_id=%s attachment_id=%s unread=%s has_attachments=%s",
            email_id,
            attachment_id,
            unread,
            has_attachments,
        )

        if attachment_id and not email_id:
            raise typer.BadParameter("--attachment requires an email_id argument.")
        if not email_id and not (unread or has_attachments):
            raise typer.BadParameter("Provide an email_id or filters like --unread/--has-attachments.")

        token_cache = TokenCache(settings.storage.token_file)
        authenticator = GraphAuthenticator.from_settings(settings.azure, token_cache=token_cache)
        graph_client = await authenticator.get_client()

        async with get_session(settings.database.url) as session:
            email_repo = EmailRepository(session)
            attachment_repo = AttachmentRepository(session)
            handler = AttachmentHandler(
                graph_client,
                Path(settings.storage.attachments_dir),
                attachment_repo,
            )

            if email_id:
                await _download_for_single_email(handler, email_id, attachment_id)
                return

            is_read = None if not unread else False
            attachments_filter = None if not has_attachments else True
            emails = await email_repo.search(is_read=is_read, has_attachments=attachments_filter)
            await _download_for_filtered_emails(handler, emails)

    except AuthenticationError as e:
        _console_print(
            Panel.fit(
                f"Authentication failed\n\n{str(e)}\n\nRun 'outmylook login' to authenticate.",
                title="Authentication Required",
                border_style="red",
            ),
            level="error",
        )
        raise typer.Exit(code=1)
    except typer.BadParameter:
        raise
    except Exception as e:
        _render_error("Download", "Error downloading attachments", e)
        raise typer.Exit(code=1)


async def _download_nomina_async(
    hours: int,
    folder: str,
    sender: Optional[str],
    subject: Optional[str],
) -> None:
    """Async implementation of download-nomina command."""
    try:
        settings = get_settings()
        _setup_logging(settings)
        settings.ensure_directories()
        logger.debug(
            "Starting download-nomina: hours=%s folder=%s sender=%s subject=%s",
            hours,
            folder,
            sender,
            subject,
        )

        token_cache = TokenCache(settings.storage.token_file)
        authenticator = GraphAuthenticator.from_settings(settings.azure, token_cache=token_cache)
        graph_client = await authenticator.get_client()

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        email_filter = EmailFilter().received_after(cutoff)

        async with get_session(settings.database.url) as session:
            email_repo = EmailRepository(session)
            attachment_repo = AttachmentRepository(session)
            email_client = EmailClient(graph_client, email_repository=email_repo)
            attachment_handler = AttachmentHandler(
                graph_client,
                Path(settings.storage.attachments_dir),
                attachment_repo,
            )

            emails = await _fetch_recent_emails(email_client, folder, email_filter)
            matched = _filter_nomina_emails(emails, hours=hours, sender=sender, subject=subject)
            if not matched:
                return

            total_downloaded = await _download_nomina_attachments(attachment_handler, matched)
            _render_nomina_summary(total_downloaded, len(matched))

    except AuthenticationError as e:
        _console_print(
            Panel.fit(
                f"Authentication failed\n\n{str(e)}\n\nRun 'outmylook login' to authenticate.",
                title="Authentication Required",
                border_style="red",
            ),
            level="error",
        )
        raise typer.Exit(code=1)
    except typer.BadParameter:
        raise
    except Exception as e:
        _render_error("Download Nomina", "Error downloading payroll attachments", e)
        raise typer.Exit(code=1)


async def _list_async(
    limit: Optional[int],
    offset: int,
    from_address: Optional[str],
    subject: Optional[str],
    after: Optional[str],
    before: Optional[str],
    unread: bool,
    read: bool,
    has_attachments: bool,
    show_ids: bool,
) -> None:
    """Async implementation of list command."""
    try:
        settings = get_settings()
        _setup_logging(settings)
        settings.ensure_directories()
        logger.debug(
            "Listing emails: limit=%s offset=%s from=%s subject=%s after=%s before=%s unread=%s read=%s has_attachments=%s",
            limit,
            offset,
            from_address,
            subject,
            after,
            before,
            unread,
            read,
            has_attachments,
        )

        filters, has_conditions = _build_local_filters(
            from_address=from_address,
            subject=subject,
            after=after,
            before=before,
            unread=unread,
            read=read,
            has_attachments=has_attachments,
        )

        async with get_session(settings.database.url) as session:
            repository = EmailRepository(session)
            if has_conditions:
                emails = await repository.search(**filters)
                emails = _apply_offset_limit(emails, limit=limit, offset=offset)
            else:
                emails = await repository.list_all(limit=limit, offset=offset)

        if not emails:
            _console_print(
                Panel.fit(
                    "No stored emails found.",
                    title="List",
                    border_style="yellow",
                ),
                level="summary",
            )
            return

        if _OUTPUT.quiet:
            if show_ids:
                _emit_email_ids(emails)
            else:
                _console_print(
                    Panel.fit(
                        f"✓ Found {len(emails)} stored email(s).",
                        title="List",
                        border_style="green",
                    ),
                    level="summary",
                )
            return

        table = build_email_table(emails, title="Stored Emails", include_id=True, include_read=False)
        _console_print(table)
        if show_ids:
            _emit_email_ids(emails)

    except typer.BadParameter:
        raise
    except Exception as e:
        _render_error("List", "Error listing emails", e)
        raise typer.Exit(code=1)


async def _export_async(
    output_path: Path,
    fmt: str,
    from_address: Optional[str],
    subject: Optional[str],
    after: Optional[str],
    before: Optional[str],
    unread: bool,
    read: bool,
    has_attachments: bool,
) -> None:
    """Async implementation of export command."""
    try:
        settings = get_settings()
        _setup_logging(settings)
        settings.ensure_directories()
        logger.debug(
            "Exporting emails: output=%s format=%s from=%s subject=%s after=%s before=%s unread=%s read=%s has_attachments=%s",
            output_path,
            fmt,
            from_address,
            subject,
            after,
            before,
            unread,
            read,
            has_attachments,
        )

        format_value = _normalize_export_format(fmt)
        filters, has_conditions = _build_local_filters(
            from_address=from_address,
            subject=subject,
            after=after,
            before=before,
            unread=unread,
            read=read,
            has_attachments=has_attachments,
        )

        async with get_session(settings.database.url) as session:
            repository = EmailRepository(session)
            if has_conditions:
                emails = await repository.search(**filters)
            else:
                emails = await repository.list_all(limit=None, offset=0)

        export_emails(emails, output_path, format_value)
        _console_print(
            Panel.fit(
                f"✓ Exported {len(emails)} email(s) to:\n{output_path}",
                title="Export",
                border_style="green",
            ),
            level="summary",
        )

    except typer.BadParameter:
        raise
    except Exception as e:
        _render_error("Export", "Error exporting emails", e)
        raise typer.Exit(code=1)


async def _download_for_single_email(
    handler: AttachmentHandler,
    email_id: str,
    attachment_id: Optional[str],
) -> None:
    if attachment_id:
        path = await handler.download_attachment(email_id, attachment_id)
        _console_print(
            Panel.fit(
                f"✓ Downloaded attachment to:\n{path}",
                title="Download",
                border_style="green",
            ),
            level="summary",
        )
        return

    paths = await handler.download_all_for_email(email_id)
    if not paths:
        _console_print(
            Panel.fit(
                f"No attachments found for email '{email_id}'.",
                title="Download",
                border_style="yellow",
            ),
            level="summary",
        )
        return

    _console_print(
        Panel.fit(
            f"✓ Downloaded {len(paths)} attachment(s).",
            title="Download",
            border_style="green",
        ),
        level="summary",
    )


async def _download_for_filtered_emails(handler: AttachmentHandler, emails: list[EmailModel]) -> None:
    if not emails:
        _console_print(
            Panel.fit(
                "No emails matched the requested filters.",
                title="Download",
                border_style="yellow",
            ),
            level="summary",
        )
        return

    total_paths: list[Path] = []
    for email in emails:
        total_paths.extend(await handler.download_all_for_email(email.id))

    _console_print(
        Panel.fit(
            f"✓ Downloaded {len(total_paths)} attachment(s) from {len(emails)} email(s).",
            title="Download",
            border_style="green",
        ),
        level="summary",
    )


def _build_local_filters(
    *,
    from_address: Optional[str],
    subject: Optional[str],
    after: Optional[str],
    before: Optional[str],
    unread: bool,
    read: bool,
    has_attachments: bool,
) -> tuple[EmailSearchFilters, bool]:
    sender = _normalize_text_filter(from_address, "Sender")
    subject_value = _normalize_text_filter(subject, "Subject")
    date_from = _parse_date_input(after, "after") if after is not None else None
    date_to = _parse_date_input(before, "before") if before is not None else None
    if date_from and date_to and date_from > date_to:
        raise typer.BadParameter("--after must be before or equal to --before.")

    is_read = _resolve_read_value(read, unread)
    attachments_value = True if has_attachments else None
    has_conditions = any(
        [
            sender is not None,
            subject_value is not None,
            date_from is not None,
            date_to is not None,
            is_read is not None,
            attachments_value is not None,
        ]
    )

    return (
        EmailSearchFilters(
            sender=sender,
            subject=subject_value,
            date_from=date_from,
            date_to=date_to,
            is_read=is_read,
            has_attachments=attachments_value,
        ),
        has_conditions,
    )


def _normalize_text_filter(value: Optional[str], label: str) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        raise typer.BadParameter(f"{label} filter cannot be empty.")
    return trimmed


def _resolve_read_value(read: bool, unread: bool) -> Optional[bool]:
    if read and unread:
        raise typer.BadParameter("Choose only one of --read or --unread.")
    if read:
        return True
    if unread:
        return False
    return None


def _apply_offset_limit(
    emails: list[EmailModel],
    *,
    limit: Optional[int],
    offset: int,
) -> list[EmailModel]:
    if offset:
        emails = emails[offset:]
    if limit is not None:
        emails = emails[:limit]
    return emails


def _normalize_export_format(value: str) -> str:
    lowered = value.lower()
    if lowered not in SUPPORTED_FORMATS:
        raise typer.BadParameter(f"Unsupported export format: {value}")
    return lowered


def _normalize_graph_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = "".join(value.split())
    return normalized or None


async def _fetch_recent_emails(
    email_client: EmailClient,
    folder: str,
    email_filter: EmailFilter,
) -> list[Any]:
    emails: list[Any] = []
    skip = 0
    while True:
        batch = await email_client.list_emails(
            folder=folder,
            limit=NOMINA_BATCH_SIZE,
            skip=skip,
            email_filter=email_filter,
        )
        if not batch:
            break
        emails.extend(batch)
        if len(batch) < NOMINA_BATCH_SIZE:
            break
        skip += NOMINA_BATCH_SIZE
    return emails


def _matches_nomina_criteria(email: Any, *, sender: Optional[str], subject: Optional[str]) -> bool:
    sender_obj = getattr(email, "sender", None)
    sender_value = getattr(sender_obj, "address", "") if sender_obj is not None else ""
    subject_value = getattr(email, "subject", "") or ""
    sender_match = sender and sender_value.lower() == sender.lower()
    subject_match = subject and subject.casefold() in subject_value.casefold()
    return bool(sender_match or subject_match)


def _format_nomina_date(received_at: datetime) -> str:
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    return received_at.date().strftime("%Y_%m_%d")


def _render_nomina_empty(message: str) -> None:
    _console_print(
        Panel.fit(message, title="Download Nomina", border_style="yellow"),
        level="summary",
    )


def _render_nomina_summary(downloaded: int, matched: int) -> None:
    _console_print(
        Panel.fit(
            f"✓ Downloaded {downloaded} attachment(s) from {matched} email(s).",
            title="Download Nomina",
            border_style="green",
        ),
        level="summary",
    )


def _filter_nomina_emails(
    emails: list[Any],
    *,
    hours: int,
    sender: Optional[str],
    subject: Optional[str],
) -> list[Any]:
    if not emails:
        _render_nomina_empty(f"No emails received in the last {hours} hours.")
        return []
    matched = [email for email in emails if _matches_nomina_criteria(email, sender=sender, subject=subject)]
    if not matched:
        _render_nomina_empty(f"No matching emails found in the last {hours} hours.")
    return matched


async def _download_nomina_attachments(handler: AttachmentHandler, emails: list[Any]) -> int:
    total_downloaded = 0
    for email in emails:
        subject_line = email.subject or "(no subject)"
        if not email.has_attachments:
            if not _OUTPUT.quiet:
                _console_print(f"No attachments for {subject_line}", level="summary")
            continue
        paths = await handler.download_all_for_email(email.id)
        renamed = [_rename_nomina_attachment(path, email.received_at) for path in paths]
        total_downloaded += len(renamed)
        if not _OUTPUT.quiet:
            _console_print(
                f"Downloaded {len(renamed)} attachment(s) for {subject_line}",
                level="summary",
            )
    return total_downloaded


def _ensure_unique_name(parent: Path, base: str, suffix: str) -> Path:
    candidate = parent / f"{base}{suffix}"
    if not candidate.exists():
        return candidate
    for counter in range(1, 1000):
        candidate = parent / f"{base}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Unable to resolve unique filename for {base}{suffix}")


def _rename_nomina_attachment(path: Path, received_at: datetime) -> Path:
    base = f"Nomina_{_format_nomina_date(received_at)}"
    if path.stem.startswith(base):
        return path
    target = _ensure_unique_name(path.parent, base, path.suffix)
    path.rename(target)
    return target


def _emit_email_ids(emails: Iterable[Any]) -> None:
    ids = [str(getattr(email, "id", "")) for email in emails if getattr(email, "id", None)]
    if not ids:
        return
    _console_print("Email IDs (copy/paste):", level="summary")
    _console_print("\n".join(ids), level="summary")


async def _get_email_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(EmailModel))
    return int(result.scalar() or 0)


def _format_database_label(database_url: str, email_count: int) -> str:
    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "")
        return f"{Path(db_path).expanduser()} ({email_count} emails)"
    return f"{database_url} ({email_count} emails)"


def _get_attachment_stats(attachments_dir: Path) -> tuple[int, int]:
    if not attachments_dir.exists():
        return (0, 0)
    count = 0
    size = 0
    for path in attachments_dir.rglob("*"):
        if path.is_file():
            count += 1
            size += path.stat().st_size
    return count, size


def _build_email_filter(
    *,
    from_address: Optional[str],
    subject: Optional[str],
    after: Optional[str],
    before: Optional[str],
    unread: bool,
    read: bool,
    has_attachments: bool,
) -> Optional[EmailFilter]:
    """Build an EmailFilter from CLI options."""
    filter_builder = EmailFilter()
    has_conditions = False

    if _apply_optional_text_filter(filter_builder.from_address, from_address):
        has_conditions = True
    if _apply_optional_text_filter(filter_builder.subject_contains, subject):
        has_conditions = True

    parsed_after = _apply_optional_date_filter(filter_builder.received_after, after, "after")
    parsed_before = _apply_optional_date_filter(filter_builder.received_before, before, "before")
    if parsed_after is not None:
        has_conditions = True
    if parsed_before is not None:
        has_conditions = True
    if parsed_after and parsed_before and parsed_after > parsed_before:
        raise typer.BadParameter("--after must be before or equal to --before.")

    if _apply_read_filter(filter_builder, read, unread):
        has_conditions = True
    if has_attachments:
        filter_builder.has_attachments(True)
        has_conditions = True

    return filter_builder if has_conditions else None


def _apply_optional_text_filter(apply_func: Callable[[str], EmailFilter], value: Optional[str]) -> bool:
    if value is None:
        return False
    try:
        apply_func(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    return True


def _apply_optional_date_filter(
    apply_func: Callable[[datetime], EmailFilter],
    value: Optional[str],
    label: str,
) -> Optional[datetime]:
    if value is None:
        return None
    parsed = _parse_date_input(value, label)
    apply_func(parsed)
    return parsed


def _apply_read_filter(filter_builder: EmailFilter, read: bool, unread: bool) -> bool:
    if read and unread:
        raise typer.BadParameter("Choose only one of --read or --unread.")
    if read:
        filter_builder.is_read(True)
        return True
    if unread:
        filter_builder.is_read(False)
        return True
    return False


def _parse_date_input(value: str, label: str) -> datetime:
    """Parse a date or datetime string for filtering."""
    raw = value.strip()
    if not raw:
        raise typer.BadParameter(f"{label} date cannot be empty.")
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"

    parsed = None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(raw)
            parsed = datetime.combine(parsed_date, time.min)
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid {label} date '{value}'. Use YYYY-MM-DD or ISO-8601 datetime.") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def main() -> None:
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
