# Database Guide

This document explains how OutMyLook stores email data, how to configure the
persistence layer, and how to manage schema changes.

## Overview

OutMyLook stores fetched email metadata in a local database. The default
configuration uses SQLite and automatically creates tables on first run.
The database layer is asynchronous and uses SQLAlchemy with the aiosqlite
driver for SQLite.

Key behaviors:
- Tables are created automatically on first use.
- Fetched emails are deduplicated by Graph message ID.
- Existing rows are updated when a matching ID is fetched again.
- Attachments are modeled but not yet populated by the fetch flow.

## Storage Location

By default, the database is created at:

```
~/.outmylook/emails.db
```

You can override the location using the `database.url` setting in
`config/config.yaml` or by setting `DATABASE_URL` when running migrations.

## Schema

### emails

Stores message metadata and the selected payload fields from Microsoft Graph.

Columns:
- `id` (TEXT, primary key) Graph message ID
- `subject` (TEXT)
- `sender_email` (TEXT, required)
- `sender_name` (TEXT)
- `received_at` (TIMESTAMP, required)
- `body_preview` (TEXT)
- `body_content` (TEXT)
- `is_read` (BOOLEAN)
- `has_attachments` (BOOLEAN)
- `folder_id` (TEXT)
- `created_at` (TIMESTAMP, default current time)
- `updated_at` (TIMESTAMP, updated on change)

Indexes:
- `idx_emails_sender` on `sender_email`
- `idx_emails_received` on `received_at`
- `idx_emails_folder` on `folder_id`

### attachments

Tracks attachment metadata for future download support.

Columns:
- `id` (TEXT, primary key) attachment ID
- `email_id` (TEXT, FK -> emails.id)
- `name` (TEXT)
- `content_type` (TEXT)
- `size` (INTEGER)
- `local_path` (TEXT)
- `downloaded_at` (TIMESTAMP)
- `created_at` (TIMESTAMP, default current time)

Indexes:
- `idx_attachments_email` on `email_id`

The attachment download flow updates `local_path` and `downloaded_at` so the
system can skip already-downloaded files.

## How Persistence Works

When you run `fetch`, the CLI creates a database session and passes an
`EmailRepository` to the `EmailClient`. After messages are fetched and mapped
into `Email` models, the repository bulk-saves them:

- New IDs are inserted.
- Existing IDs are updated with the latest values.
- Duplicate IDs in a single fetch are collapsed to one row.

This flow keeps the database in sync with the latest Graph metadata without
creating duplicates.

When attachments are listed or downloaded, the attachment metadata is saved or
updated in the `attachments` table. Downloads also update `local_path` and
`downloaded_at` for tracking and deduplication.

## Configuration

The database URL is configured in `config/config.yaml`:

```yaml
database:
  url: "sqlite:///~/.outmylook/emails.db"
```

Notes:
- SQLite paths using `~/` are expanded automatically.
- For non-SQLite databases, you must use an async-capable driver URL and
  install the driver. Examples:
  - PostgreSQL: `postgresql+asyncpg://user:pass@localhost/dbname`
  - MySQL: `mysql+aiomysql://user:pass@localhost/dbname`

## Migrations (Alembic)

Alembic is configured under `src/database/migrations/` with `alembic.ini`
pointing at the default SQLite file. You can override the database URL at
runtime using `DATABASE_URL`.

Common commands (run from the repo root):

```bash
# Upgrade to the latest schema
alembic upgrade head

# Create a new migration after editing models
alembic revision --autogenerate -m "describe change"
```

If you are using a non-SQLite database, set `DATABASE_URL` before running
Alembic:

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/dbname"
alembic upgrade head
```

## Repository Usage (Developers)

If you want to query stored emails in code, use the repository:

```python
from src.database.repository import EmailRepository, get_session

async with get_session("sqlite:///~/.outmylook/emails.db") as session:
    repo = EmailRepository(session)
    emails = await repo.list_all(limit=50)
```

Available repository methods:
- `save(email)`
- `save_many(emails)`
- `get_by_id(email_id)`
- `list_all(limit, offset, order_by)`
- `search(sender, subject, date_from, date_to)`

## Inspecting Data

For SQLite, you can inspect the database directly:

```bash
sqlite3 ~/.outmylook/emails.db
sqlite> .tables
sqlite> SELECT id, sender_email, subject FROM emails ORDER BY received_at DESC LIMIT 5;
```

## Troubleshooting

- **Database not created**: Ensure you ran a command that touches the database
  (like `fetch`) and that `settings.ensure_directories()` has permissions to
  create `~/.outmylook`.
- **Missing greenlet**: If you see `ValueError: the greenlet library is required`,
  install dependencies again (`pip install -r requirements.txt`).
- **Migrations fail**: Verify `DATABASE_URL` points to a valid database and the
  async driver is installed.

## Testing

Database tests are in:
- `tests/test_database.py`
- `tests/test_repository.py`

Run:

```bash
pytest tests/test_database.py tests/test_repository.py
```
