"""Download all attachments from emails matching a filter."""

import asyncio
from pathlib import Path

from src.attachments import AttachmentHandler
from src.auth import GraphAuthenticator, TokenCache
from src.config.settings import get_settings
from src.database.repository import AttachmentRepository, EmailRepository, get_session
from src.email import EmailClient, EmailFilter


async def main() -> None:
    """Authenticate, filter emails, and download their attachments."""
    settings = get_settings()
    settings.ensure_directories()

    token_cache = TokenCache(settings.storage.token_file)
    authenticator = GraphAuthenticator.from_settings(settings.azure, token_cache=token_cache)
    graph_client = await authenticator.get_client()

    async with get_session(settings.database.url) as session:
        email_repo = EmailRepository(session)
        attachment_repo = AttachmentRepository(session)
        email_client = EmailClient(graph_client, email_repository=email_repo)
        attachment_handler = AttachmentHandler(
            graph_client,
            Path(settings.storage.attachments_dir),
            attachment_repo,
        )

        email_filter = EmailFilter().has_attachments().is_read(False)
        emails = await email_client.list_emails(folder="inbox", limit=25, email_filter=email_filter)

        for email in emails:
            paths = await attachment_handler.download_all_for_email(email.id)
            subject = email.subject or "(no subject)"
            print(f"Downloaded {len(paths)} attachments for {subject}")


if __name__ == "__main__":
    asyncio.run(main())
