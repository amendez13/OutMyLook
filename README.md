# OutMyLook

![CI](https://github.com/your-username/OutMyLook/workflows/CI/badge.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Coverage](https://img.shields.io/badge/coverage-95%25-green.svg)

A Python application for managing Microsoft Outlook emails using the Microsoft Graph API.

## Features

- **OAuth2 Authentication**: Secure authentication with Microsoft Graph using Device Code Flow
- **Token Caching**: Persistent token storage for seamless re-authentication
- **CLI Interface**: User-friendly command-line interface for email management
- **Local Querying & Export**: List stored emails and export to JSON/CSV
- **Automatic Token Refresh**: Tokens automatically refreshed before expiration
- **Persistent Database Storage**: Fetch results are stored locally for later querying
- **Attachment Downloads**: Download and track email attachments locally

## Prerequisites

- Python 3.10 or higher
- pip (Python package installer)
- Microsoft account (@outlook.com, @hotmail.com, @live.com, or organizational account)
- Azure AD application registration (see [Setup Guide](docs/SETUP.md) for step-by-step Azure setup)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/OutMyLook.git
cd OutMyLook
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

> **Important**: Always ensure the virtual environment is activated (you should see `(venv)` in your terminal) before installing dependencies or running the application.

4. Configure the application:
```bash
cp config/config.example.yaml config/config.yaml
# Edit config/config.yaml with your settings
```

For a full Azure app registration walkthrough (Device Code Flow, permissions, and public client flows),
see [docs/SETUP.md](docs/SETUP.md).

## Quick Start

Authenticate, then fetch the latest emails:

```bash
python -m src.main login
python -m src.main fetch --folder inbox --limit 10
```

## Usage

### Authentication

```bash
python -m src.main login
python -m src.main status
python -m src.main logout
```

The login command displays a device code URL. Visit the URL, enter the code, and grant permissions. Tokens are cached at the path configured in `storage.token_file`.

### Fetching Email

```bash
python -m src.main fetch --folder inbox --limit 25 --skip 0
python -m src.main fetch --from "boss@company.com" --subject "invoice"
python -m src.main fetch --after 2025-01-01 --unread --has-attachments
```

Fetched messages are persisted to the local database (default `~/.outmylook/emails.db`). Duplicate Graph IDs are updated in place.

### Listing Stored Emails

```bash
python -m src.main list
python -m src.main list --from "amazon.com" --after 2025-01-01
python -m src.main list --limit 50 --offset 100
```

### Exporting Stored Emails

```bash
python -m src.main export exports/emails.json --format json
python -m src.main export exports/emails.csv --format csv --unread
```

### Downloading Attachments

```bash
python -m src.main download <email_id>
python -m src.main download <email_id> --attachment <attachment_id>
python -m src.main download --unread --has-attachments
```

Attachments are stored under `storage.attachments_dir` (default `~/.outmylook/attachments`).

### Output Controls

Global flags apply to all commands:

- `--verbose`: Enable debug logging and show more detail.
- `--quiet`: Suppress non-essential output (errors and summaries only).

### Example Scripts

See the `examples/` directory:

- `examples/fetch_recent.py`
- `examples/download_attachments.py`
- `examples/export_to_csv.py`

## CLI Command Reference

| Command | Purpose | Common options |
| --- | --- | --- |
| `login` | Authenticate with Microsoft Graph | `--config` |
| `status` | Show auth, database, and attachment status | |
| `logout` | Clear cached tokens | |
| `fetch` | Fetch emails from Microsoft Graph | `--folder`, `--limit`, `--skip`, `--from`, `--subject`, `--after`, `--before`, `--read`, `--unread`, `--has-attachments` |
| `list` | Query stored emails locally | `--limit`, `--offset`, `--from`, `--subject`, `--after`, `--before`, `--read`, `--unread`, `--has-attachments` |
| `export` | Export stored emails to JSON/CSV | `--format`, filters from `list` |
| `download` | Download attachments | `<email_id>`, `--attachment`, `--unread`, `--has-attachments` |

Run `python -m src.main --help` or `python -m src.main <command> --help` for full details.

## Configuration Options

Configuration is stored in `config/config.yaml`. See `config/config.example.yaml` for all available options.

```yaml
azure:
  client_id: "your-azure-app-client-id"
  tenant: "common"
  scopes:
    - "https://graph.microsoft.com/Mail.Read"
    - "https://graph.microsoft.com/User.Read"
    - "offline_access"

database:
  url: "sqlite:///~/.outmylook/emails.db"

storage:
  attachments_dir: "~/.outmylook/attachments"
  token_file: "~/.outmylook/tokens.json"

logging:
  level: "INFO"
```

You can override settings with environment variables using these prefixes:

- `AZURE_CLIENT_ID`, `AZURE_TENANT`, `AZURE_SCOPES`
- `DATABASE_URL`
- `STORAGE_ATTACHMENTS_DIR`, `STORAGE_TOKEN_FILE`
- `LOGGING_LEVEL`

For database setup and migrations, see [Database Guide](docs/DATABASE.md).

## Troubleshooting

- **Authentication fails or client_id missing**: Ensure `azure.client_id` is set in `config/config.yaml` or `AZURE_CLIENT_ID` is exported.
- **Device code flow never completes**: Confirm the account used to sign in has granted consent to the app registration.
- **Token cache is stale**: Delete the file at `storage.token_file` and re-run `login`.
- **SQLite database is locked**: Make sure no other process is using the DB; restart any running fetch/list/export commands.
- **Attachments not downloading**: Confirm the `Mail.Read` scope is present and the email actually has attachments.

## Project Structure

```
OutMyLook/
├── .github/workflows/    # CI/CD configuration
├── .claude/              # Claude Code configuration
├── config/               # Configuration files
├── docs/                 # Documentation
├── examples/             # Example scripts
├── src/                  # Source code
├── tests/                # Test files
├── CLAUDE.md             # AI assistant guidance
├── README.md             # This file
├── pyproject.toml        # Tool configuration
└── requirements.txt      # Dependencies
```

## Development

### Setup Development Environment

```bash
pip install -r requirements-dev.txt
pre-commit install
```

### Running Tests

```bash
pytest
pytest --cov=src --cov-report=term-missing
```

### Code Quality

This project uses:
- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking
- **bandit** for security scanning
- **pip-audit** for dependency vulnerability checking

All checks run automatically via pre-commit hooks and CI.

## CI/CD

GitHub Actions runs the following checks on every push and PR:

1. **Lint**: Black, isort, flake8, mypy
2. **Test**: pytest across Python 3.10, 3.11, 3.12
3. **Coverage**: 95% minimum coverage
4. **Security**: bandit and pip-audit

See [docs/CI.md](docs/CI.md) for details.

## Documentation

- [Documentation Index](docs/INDEX.md) - All documentation
- [Setup Guide](docs/SETUP.md) - Installation and configuration
- [Usage Guide](docs/USAGE.md) - CLI usage and examples
- [Database Guide](docs/DATABASE.md) - Local storage and migrations
- [Architecture](docs/ARCHITECTURE.md) - Technical design and components

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit your changes (`git commit -m 'feat: add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request
