"""Download payroll attachments for recent emails."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.attachments import AttachmentHandler
from src.auth import GraphAuthenticator, TokenCache
from src.config.settings import get_settings
from src.database.repository import AttachmentRepository, EmailRepository, get_session
from src.email import EmailClient, EmailFilter

SENDER_ADDRESS = "noreply.laboral.bcn@bdo.es"
SUBJECT_FRAGMENT = "Hojas de Salario"
LOOKBACK_HOURS = 24
BATCH_SIZE = 100


def _matches_criteria(sender: str, subject: str) -> bool:
    sender_match = sender.lower() == SENDER_ADDRESS.lower()
    subject_match = SUBJECT_FRAGMENT.casefold() in subject.casefold()
    return sender_match or subject_match


def _format_received_date(received_at: datetime) -> str:
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    return received_at.date().strftime("%Y_%m_%d")


def _ensure_unique_name(parent: Path, base: str, suffix: str) -> Path:
    candidate = parent / f"{base}{suffix}"
    if not candidate.exists():
        return candidate
    for counter in range(1, 1000):
        candidate = parent / f"{base}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Unable to resolve unique filename for {base}{suffix}")


def _rename_attachment(path: Path, received_at: datetime) -> Path:
    base = f"Nomina_{_format_received_date(received_at)}"
    if path.stem.startswith(base):
        return path
    target = _ensure_unique_name(path.parent, base, path.suffix)
    path.rename(target)
    return target


async def _fetch_recent_emails(email_client: EmailClient) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    email_filter = EmailFilter().received_after(cutoff)
    emails = []
    skip = 0
    while True:
        batch = await email_client.list_emails(
            folder="inbox",
            limit=BATCH_SIZE,
            skip=skip,
            email_filter=email_filter,
        )
        if not batch:
            break
        emails.extend(batch)
        if len(batch) < BATCH_SIZE:
            break
        skip += BATCH_SIZE
    return emails


async def main() -> None:
    """Fetch recent emails and download payroll attachments."""
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

        emails = await _fetch_recent_emails(email_client)
        if not emails:
            print("No emails received in the last 24 hours.")
            return

        matched = [email for email in emails if _matches_criteria(email.sender.address or "", email.subject or "")]
        if not matched:
            print("No matching emails found in the last 24 hours.")
            return

        for email in matched:
            subject = email.subject or "(no subject)"
            if not email.has_attachments:
                print(f"No attachments for {subject}")
                continue
            paths = await attachment_handler.download_all_for_email(email.id)
            renamed_paths = [_rename_attachment(path, email.received_at) for path in paths]
            print(f"Downloaded {len(renamed_paths)} attachment(s) for {subject}")


if __name__ == "__main__":
    asyncio.run(main())
