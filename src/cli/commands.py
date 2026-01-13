"""CLI commands for OutMyLook."""

import asyncio
import logging
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Annotated, Callable, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.attachments import AttachmentHandler
from src.auth import AuthenticationError, GraphAuthenticator, TokenCache
from src.config.settings import get_settings
from src.database.models import EmailModel
from src.database.repository import AttachmentRepository, EmailRepository, get_session
from src.email import Email, EmailClient, EmailFilter

app = typer.Typer(help="OutMyLook - Microsoft Outlook email management tool")
console = Console()
logger = logging.getLogger(__name__)


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
        settings.setup_logging()

        # Check if already authenticated
        token_cache = TokenCache(settings.storage.token_file)

        if token_cache.has_valid_token():
            token_info = await token_cache.get_token_info()
            if token_info:
                console.print(
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
            console.print("[yellow]Cleared existing token[/yellow]\n")

        # Create authenticator
        authenticator = GraphAuthenticator.from_settings(settings.azure, token_cache=token_cache)

        # Display authentication instructions
        console.print(
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

                console.print()
                display_name = user.display_name if user else "Unknown"
                email = user.user_principal_name if user else "Unknown"
                console.print(
                    Panel.fit(
                        f"✓ Authentication successful!\n\n"
                        f"Logged in as: {display_name}\n"
                        f"Email: {email}\n\n"
                        f"Token cached to: {settings.storage.token_file}",
                        title="Success",
                        border_style="green",
                    )
                )

            except AuthenticationError as e:
                console.print(
                    Panel.fit(
                        f"✗ Authentication failed\n\n{str(e)}",
                        title="Error",
                        border_style="red",
                    )
                )
                raise typer.Exit(code=1)

    except Exception as e:
        logger.exception("Login failed")
        console.print(
            Panel.fit(
                f"✗ Unexpected error during login\n\n{str(e)}",
                title="Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)


@app.command()
def logout() -> None:
    """Logout and clear cached authentication tokens."""
    asyncio.run(_logout_async())


async def _logout_async() -> None:
    """Async implementation of logout command."""
    try:
        settings = get_settings()
        token_cache = TokenCache(settings.storage.token_file)

        if not token_cache.has_valid_token():
            console.print(
                Panel.fit(
                    "No active session found. You are not logged in.",
                    title="Logout",
                    border_style="yellow",
                )
            )
            return

        # Clear the token
        await token_cache.clear()

        console.print(
            Panel.fit(
                "✓ Successfully logged out\n\nYour authentication token has been removed.",
                title="Logout",
                border_style="green",
            )
        )

    except Exception as e:
        logger.exception("Logout failed")
        console.print(Panel.fit(f"✗ Error during logout\n\n{str(e)}", title="Error", border_style="red"))
        raise typer.Exit(code=1)


@app.command()
def status() -> None:
    """Check authentication status and token information."""
    asyncio.run(_status_async())


async def _status_async() -> None:
    """Async implementation of status command."""
    try:
        settings = get_settings()
        token_cache = TokenCache(settings.storage.token_file)

        if not token_cache.has_valid_token():
            console.print(
                Panel.fit(
                    "✗ Not authenticated\n\n" "Run 'outmylook login' to authenticate with Microsoft Graph.",
                    title="Authentication Status",
                    border_style="red",
                )
            )
            return

        token_info = await token_cache.get_token_info()

        if token_info:
            expiring_soon = token_cache.is_token_expiring_soon()
            status_icon = "⚠" if expiring_soon else "✓"
            border_color = "yellow" if expiring_soon else "green"

            console.print(
                Panel.fit(
                    f"{status_icon} Authenticated\n\n"
                    f"Token expires: {token_info['expires_at']}\n"
                    f"Time until expiry: {token_info['seconds_until_expiry']} seconds\n"
                    f"Scopes: {', '.join(token_info['scopes'])}\n"
                    f"Cached at: {token_info['cached_at']}",
                    title="Authentication Status",
                    border_style=border_color,
                )
            )

            if expiring_soon:
                console.print(
                    "\n[yellow]Note: Token is expiring soon. " "It will be refreshed automatically on next use.[/yellow]"
                )
        else:
            console.print(
                Panel.fit(
                    "✗ Token information unavailable",
                    title="Authentication Status",
                    border_style="red",
                )
            )

    except Exception as e:
        logger.exception("Status check failed")
        console.print(
            Panel.fit(
                f"✗ Error checking status\n\n{str(e)}",
                title="Error",
                border_style="red",
            )
        )
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
    asyncio.run(_fetch_async(folder, limit, skip, email_filter))


async def _fetch_async(folder: str, limit: int, skip: int, email_filter: Optional[EmailFilter]) -> None:
    """Async implementation of fetch command."""
    try:
        settings = get_settings()
        settings.setup_logging()
        settings.ensure_directories()

        token_cache = TokenCache(settings.storage.token_file)
        authenticator = GraphAuthenticator.from_settings(settings.azure, token_cache=token_cache)
        graph_client = await authenticator.get_client()

        async with get_session(settings.database.url) as session:
            repository = EmailRepository(session)
            email_client = EmailClient(graph_client, email_repository=repository)
            emails = await email_client.list_emails(folder=folder, limit=limit, skip=skip, email_filter=email_filter)

        if not emails:
            console.print(
                Panel.fit(
                    f"No emails found in '{folder}'.",
                    title="Fetch",
                    border_style="yellow",
                )
            )
            return

        _render_email_table(emails, folder)

    except AuthenticationError as e:
        console.print(
            Panel.fit(
                f"Authentication failed\n\n{str(e)}\n\nRun 'outmylook login' to authenticate.",
                title="Authentication Required",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)
    except Exception as e:
        logger.exception("Fetch failed")
        console.print(
            Panel.fit(
                f"Error fetching emails\n\n{str(e)}",
                title="Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)


@app.command()
def download(
    email_id: Annotated[Optional[str], typer.Argument(None, help="Email ID to download attachments from")] = None,
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


async def _download_async(
    email_id: Optional[str],
    attachment_id: Optional[str],
    unread: bool,
    has_attachments: bool,
) -> None:
    """Async implementation of download command."""
    try:
        settings = get_settings()
        settings.setup_logging()
        settings.ensure_directories()

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
        console.print(
            Panel.fit(
                f"Authentication failed\n\n{str(e)}\n\nRun 'outmylook login' to authenticate.",
                title="Authentication Required",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)
    except typer.BadParameter:
        raise
    except Exception as e:
        logger.exception("Download failed")
        console.print(
            Panel.fit(
                f"Error downloading attachments\n\n{str(e)}",
                title="Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)


async def _download_for_single_email(
    handler: AttachmentHandler,
    email_id: str,
    attachment_id: Optional[str],
) -> None:
    if attachment_id:
        path = await handler.download_attachment(email_id, attachment_id)
        console.print(
            Panel.fit(
                f"✓ Downloaded attachment to:\n{path}",
                title="Download",
                border_style="green",
            )
        )
        return

    paths = await handler.download_all_for_email(email_id)
    if not paths:
        console.print(
            Panel.fit(
                f"No attachments found for email '{email_id}'.",
                title="Download",
                border_style="yellow",
            )
        )
        return

    console.print(
        Panel.fit(
            f"✓ Downloaded {len(paths)} attachment(s).",
            title="Download",
            border_style="green",
        )
    )


async def _download_for_filtered_emails(handler: AttachmentHandler, emails: list[EmailModel]) -> None:
    if not emails:
        console.print(
            Panel.fit(
                "No emails matched the requested filters.",
                title="Download",
                border_style="yellow",
            )
        )
        return

    total_paths: list[Path] = []
    for email in emails:
        total_paths.extend(await handler.download_all_for_email(email.id))

    console.print(
        Panel.fit(
            f"✓ Downloaded {len(total_paths)} attachment(s) from {len(emails)} email(s).",
            title="Download",
            border_style="green",
        )
    )


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


def _render_email_table(emails: list[Email], folder: str) -> None:
    """Render fetched emails in a readable table."""
    table = Table(title=f"Emails in {folder}")
    table.add_column("Received", style="cyan")
    table.add_column("From", style="magenta")
    table.add_column("Subject", style="white")
    table.add_column("Read", justify="center")
    table.add_column("Attachments", justify="center")

    for email in emails:
        sender = email.sender.name or email.sender.address
        received = email.received_at.strftime("%Y-%m-%d %H:%M")
        subject = email.subject or "(no subject)"
        is_read = "yes" if email.is_read else "no"
        has_attachments = "yes" if email.has_attachments else "no"
        table.add_row(received, sender, subject, is_read, has_attachments)

    console.print(table)


def main() -> None:
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
