"""Fetch and display last 10 emails."""

import asyncio

from src.auth import GraphAuthenticator, TokenCache
from src.config.settings import get_settings
from src.email import EmailClient


async def main() -> None:
    """Authenticate and list recent emails from the inbox."""
    settings = get_settings()
    settings.ensure_directories()

    token_cache = TokenCache(settings.storage.token_file)
    authenticator = GraphAuthenticator.from_settings(settings.azure, token_cache=token_cache)
    graph_client = await authenticator.get_client()

    email_client = EmailClient(graph_client)
    emails = await email_client.list_emails(folder="inbox", limit=10)

    for email in emails:
        received = email.received_at.strftime("%Y-%m-%d %H:%M")
        subject = email.subject or "(no subject)"
        print(f"{received} | {email.sender.address} | {subject}")


if __name__ == "__main__":
    asyncio.run(main())
