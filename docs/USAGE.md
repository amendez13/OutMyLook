# Usage Guide

This guide explains how to run OutMyLook from the command line and what to expect
from each command.

## Quick Start

1. Configure your Azure application in `config/config.yaml` (see `docs/SETUP.md`).
2. Authenticate with Microsoft Graph.
3. Fetch emails from a folder.

```bash
python -m src.main login
python -m src.main fetch --folder inbox --limit 10
```

## Global Flags

The CLI supports global output controls that apply to all commands:

- `--verbose`: Enable debug logging and show more detail in command output.
- `--quiet`: Suppress non-essential output and show only errors or summaries.

Only one of `--verbose` or `--quiet` can be used at a time.

## Authentication Commands

### Login

```bash
python -m src.main login
```

What happens:
- The CLI prints a URL and a device code.
- Open the URL in a browser and enter the code.
- MSAL caches tokens and OutMyLook stores a non-secret auth record for reuse.

Authentication is reused via MSAL's persistent cache and a local auth record
stored at `~/.outmylook/auth_record.json`. The `storage.token_file` JSON (default
`~/.outmylook/tokens.json`) is informational for status/troubleshooting and not
used for authentication.

### Status

```bash
python -m src.main status
```

Shows authentication, database, and attachment storage status. Example output:

```
Authentication: Logged in as user@outlook.com
Token expires: 2025-01-15 14:30:00
Database: ~/.outmylook/emails.db (1,234 emails)
Attachments: ~/.outmylook/attachments (56 files, 128 MB)
```

If the token is close to expiring, the CLI warns that it will refresh on the next use.

### Logout

```bash
python -m src.main logout
```

Clears the auth record and cached token metadata so the next command will
require re-authentication.

## Fetching Email

### Fetch from a folder

```bash
python -m src.main fetch --folder inbox --limit 25 --skip 0
```

Options:
- `--folder`: Folder name or Graph folder ID (default: `inbox`).
- `--limit`: Number of messages to fetch (default: `25`).
- `--skip`: Offset for pagination (default: `0`).

The command prints a table with received time, sender, subject, read status,
and attachment presence. Empty folders are handled gracefully.
If the access token is expired but a refresh token exists, the SDK refreshes
silently. If authentication fails, run `python -m src.main login`.
Use `--ids` to print a copy-friendly list of email IDs after the table.

### Database

Every fetch persists the returned messages to the configured database. The
default SQLite file is located at `~/.outmylook/emails.db` and is created
automatically. Duplicate Graph message IDs are not re-inserted; they are
updated in place.

Configuration:

```yaml
database:
  url: "sqlite:///~/.outmylook/emails.db"
```

To use another engine, supply an async-capable SQLAlchemy URL and install the
driver (see `docs/DATABASE.md` for examples).

To inspect the stored data:

```bash
sqlite3 ~/.outmylook/emails.db
sqlite> SELECT id, sender_email, subject FROM emails ORDER BY received_at DESC LIMIT 5;
```

More examples:

```bash
# Count stored emails
sqlite3 ~/.outmylook/emails.db "SELECT COUNT(*) FROM emails;"

# Show unread messages in the last 7 days
sqlite3 ~/.outmylook/emails.db \
  "SELECT sender_email, subject, received_at FROM emails WHERE is_read = 0 AND received_at >= datetime('now','-7 days') ORDER BY received_at DESC;"
```

```bash
# Run migrations against a custom database
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/outmylook"
alembic upgrade head
```

```bash
# Fetch and persist unread messages from the last week
python -m src.main fetch --folder inbox --unread --after 2025-01-01

# Fetch messages from a sender and subject filter
python -m src.main fetch --from "boss@company.com" --subject "invoice" --has-attachments
```

See `docs/DATABASE.md` for schema details and migration commands.

## Listing Stored Emails

Use `list` to query the local database without calling Microsoft Graph.

```bash
# List all stored emails
python -m src.main list

# List with filters
python -m src.main list --from "amazon.com"
python -m src.main list --subject "order"
python -m src.main list --after 2025-01-01

# Pagination
python -m src.main list --limit 50 --offset 100

# Copy-friendly IDs
python -m src.main list --ids
```

The table includes the Graph message ID, sender, subject, received time,
and attachment status.

## Exporting Stored Emails

Use `export` to write stored emails to JSON or CSV.

```bash
# Export to JSON
python -m src.main export emails.json --format json

# Export to CSV
python -m src.main export emails.csv --format csv

# Export with filters
python -m src.main export orders.json --from "amazon.com" --format json
```

Notes:
- Filters behave the same as `list` and are applied to the local database.
- When exporting CSV with zero records, the file still includes header columns.

### Attachment downloads

Attachments are downloaded to the directory configured in `storage.attachments_dir`
(default: `~/.outmylook/attachments`). Files are stored under a per-email folder
using the original filename; conflicts add an incrementing suffix.

Basic usage:

```bash
# Download all attachments for a specific email
python -m src.main download <email_id>

# Download a specific attachment
python -m src.main download <email_id> --attachment <attachment_id>
```

Filter-based downloads:

```bash
# Download attachments for unread emails that have attachments
python -m src.main download --unread --has-attachments
```

Notes:
- Already-downloaded attachments are skipped when a stored local path exists.
- Progress is shown for each download.
- If you provide `--attachment`, you must also pass the email ID.

Troubleshooting:
- **No attachments found**: Confirm the message actually has attachments and that
  you requested the correct email ID or filters.
- **Large attachments missing content**: OutMyLook falls back to the Graph `$value`
  endpoint for large files. If you still see "content is not available", retry
  and confirm your Graph permissions allow attachment downloads.
- **Download errors**: Verify the app has permission to write to
  `storage.attachments_dir` and that the directory exists.
- **Nothing happens for filters**: Use `fetch --unread --has-attachments` first
  to populate the database, then run `download --unread --has-attachments`.

### Folder selection

The following well-known folders are recognized (case-insensitive):
- `inbox`
- `sent` / `sentitems`
- `drafts`
- `archive`
- `deleted` / `deleteditems`
- `junk` / `junkemail`
- `outbox`

If the value does not match a well-known name, the CLI attempts to resolve it
by display name. If no match is found, it is treated as a Graph folder ID.

## Configuration Notes

Configuration is read from `config/config.yaml` if present. You can also set
`OUTMYLOOK_CONFIG` to point at a custom config file.

Required values:
- `azure.client_id`: The Azure application (client) ID.

Optional values:
- `azure.tenant`: Use `common` for personal accounts, or your tenant ID.
- `azure.scopes`: Graph API scopes (defaults are set in `config/config.example.yaml`).
- `storage.token_file`: Informational token cache path (used for status output).

## Troubleshooting

- **Not authenticated**: Run `python -m src.main login`.
- **Invalid client_id**: Verify `azure.client_id` in `config/config.yaml`.
- **No emails returned**: Try a different folder or reduce `--skip`.
- **Login output is noisy**: Set `logging.level` to `WARNING` in `config/config.yaml` or use `LOGGING_LEVEL=WARNING`.
