# API Reference

This project exposes a small set of public Python classes that are useful for
scripting and automation. The CLI wraps the same APIs.

## Configuration

- `src.config.settings.get_settings()` loads configuration from `config/config.yaml`
  or environment variables and returns a `Settings` instance.

## Authentication

- `src.auth.GraphAuthenticator` handles Device Code Flow authentication and
  returns a `GraphServiceClient` via `get_client()`.
- `src.auth.TokenCache` manages cached access tokens on disk.

## Email

- `src.email.EmailClient` wraps `GraphServiceClient` and provides:
  - `list_emails()` to fetch messages with pagination and filters
  - `get_email()` to fetch a single message
  - `list_folders()` to enumerate mail folders
- `src.email.EmailFilter` builds OData filters for server-side Graph queries.

## Attachments

- `src.attachments.AttachmentHandler` lists and downloads attachments and
  records metadata in the local database.

## Database

- `src.database.repository.get_session()` yields an async SQLAlchemy session and
  creates tables if needed.
- `src.database.repository.EmailRepository` persists and queries email records.
- `src.database.repository.AttachmentRepository` persists attachment metadata.

## Example

```python
import asyncio
from src.auth import GraphAuthenticator, TokenCache
from src.config.settings import get_settings
from src.email import EmailClient


async def main() -> None:
    settings = get_settings()
    token_cache = TokenCache(settings.storage.token_file)
    client = await GraphAuthenticator.from_settings(settings.azure, token_cache=token_cache).get_client()
    emails = await EmailClient(client).list_emails(folder="inbox", limit=5)
    print([email.subject for email in emails])


if __name__ == "__main__":
    asyncio.run(main())
```
