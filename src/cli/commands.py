"""CLI commands for OutMyLook."""

import asyncio
import logging
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.auth import AuthenticationError, GraphAuthenticator, TokenCache
from src.config.settings import get_settings
from src.email import Email, EmailClient

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
    limit: int = typer.Option(25, "--limit", "-l", help="Number of emails to fetch"),
    folder: str = typer.Option("inbox", "--folder", "-f", help="Mail folder to fetch from"),
    skip: int = typer.Option(0, "--skip", help="Number of emails to skip"),
) -> None:
    """Fetch emails from Microsoft Graph."""
    asyncio.run(_fetch_async(folder, limit, skip))


async def _fetch_async(folder: str, limit: int, skip: int) -> None:
    """Async implementation of fetch command."""
    try:
        settings = get_settings()
        settings.setup_logging()

        token_cache = TokenCache(settings.storage.token_file)
        if not token_cache.has_valid_token():
            console.print(
                Panel.fit(
                    "Not authenticated. Run 'outmylook login' first.",
                    title="Authentication Required",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

        authenticator = GraphAuthenticator.from_settings(settings.azure, token_cache=token_cache)
        graph_client = await authenticator.get_client()

        email_client = EmailClient(graph_client)
        emails = await email_client.list_emails(folder=folder, limit=limit, skip=skip)

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
                f"Authentication failed\n\n{str(e)}",
                title="Error",
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
