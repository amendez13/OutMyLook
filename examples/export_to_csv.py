"""Export all stored emails to CSV."""

import asyncio
from pathlib import Path

from src.cli.exporters import export_emails
from src.config.settings import get_settings
from src.database.repository import EmailRepository, get_session


async def main() -> None:
    """Export stored emails to a CSV file."""
    settings = get_settings()

    async with get_session(settings.database.url) as session:
        repo = EmailRepository(session)
        emails = await repo.list_all()

    output_path = Path("exports/emails.csv")
    export_emails(emails, output_path, "csv")
    print(f"Exported {len(emails)} emails to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
