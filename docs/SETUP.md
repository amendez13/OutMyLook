# Setup Guide

This guide walks you through setting up OutMyLook for development or usage.

## Quick Reference

**Always activate the virtual environment before working:**
```bash
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows
```

You should see `(venv)` prefix in your terminal when it's active.

## Prerequisites

- Python 3.10 or higher
- pip (Python package installer)
- git

### Optional

- [List optional dependencies]

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/OutMyLook.git
cd OutMyLook
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows
```

### 3. Install Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies (recommended for development)
pip install -r requirements-dev.txt
```

> **Note**: The virtual environment must be activated before installing dependencies. If you see a `(venv)` prefix in your terminal, the environment is active. If not, run `source venv/bin/activate` first.

### 4. Install Pre-commit Hooks (Development Only)

```bash
# Install pre-commit hooks to enforce code quality
pre-commit install
```

Pre-commit hooks will automatically run code quality checks before each commit.

### 5. Azure App Registration (Microsoft Graph)

OutMyLook uses Microsoft Graph with Device Code Flow. You need an Azure AD app
registration to obtain a client ID. No client secret is required.

1. Go to the Azure Portal: https://portal.azure.com
2. Navigate to **Azure Active Directory** -> **App registrations** -> **New registration**.
3. Fill out the form:
   - **Name**: `OutMyLook` (or any name you prefer).
   - **Supported account types**:
     - Personal accounts: select **Accounts in any organizational directory and personal Microsoft accounts**.
     - Org-only: select the appropriate single/multi-tenant option for your organization.
   - **Redirect URI**: leave blank (Device Code Flow does not require it).
4. Click **Register**.
5. Copy the following values from the app overview:
   - **Application (client) ID** -> use for `azure.client_id`
   - **Directory (tenant) ID** -> use for `azure.tenant` (org accounts only)
6. Configure authentication:
   - Go to **Authentication**.
   - Under **Advanced settings**, enable **Allow public client flows**.
7. Add Microsoft Graph permissions:
   - Go to **API permissions** -> **Add a permission** -> **Microsoft Graph** -> **Delegated permissions**.
   - Add: `Mail.Read`, `User.Read`, and `offline_access` (under OpenID permissions).
   - If you're in an organization, click **Grant admin consent** if required.

Notes:
- If you only need read-only access to a subset of mail, adjust the scopes in `config/config.yaml`.
- For personal Microsoft accounts, keep `azure.tenant` set to `common`.
- For org-only access, set `azure.tenant` to your directory (tenant) ID.

### 6. Configure the Application

```bash
# Copy example configuration
cp config/config.example.yaml config/config.yaml

# Edit configuration with your settings
# On macOS/Linux:
nano config/config.yaml
# Or use your preferred editor
```

Attachment storage is configured under `storage.attachments_dir`. The default
path (`~/.outmylook/attachments`) is created automatically on first use.

### 7. Database Setup (Optional)

OutMyLook stores fetched emails in a local database by default. For SQLite,
no extra setup is required; the file is created on first use.

If you want to use another database engine, set `database.url` in
`config/config.yaml` to an async-capable SQLAlchemy URL and install the driver.
Examples:

```yaml
database:
  url: "postgresql+asyncpg://user:pass@localhost/dbname"
```

For schema management, Alembic is preconfigured in `alembic.ini`. You can
run migrations manually:

```bash
alembic upgrade head
```

See `docs/DATABASE.md` for more detail.

### 8. Verify Installation

```bash
# Run tests to verify setup
pytest

# Or run the application
python -m src.main --help
```

## Configuration

### config/config.yaml

The main configuration file. See `config/config.example.yaml` for all available options.

```yaml
# Application settings
app:
  debug: false
  log_level: INFO

# Add your configuration sections
```

### Environment Variables

You can also configure the application using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_DEBUG` | Enable debug mode | `false` |
| `APP_LOG_LEVEL` | Logging level | `INFO` |

## Development Setup

### Verify Pre-commit Hooks

If you installed the development dependencies and pre-commit hooks (step 4), verify they work:

```bash
# Run all hooks manually
pre-commit run --all-files
```

### IDE Setup

#### VS Code

Recommended extensions:
- Python
- Pylance
- Black Formatter
- isort

Settings (`.vscode/settings.json`):
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "[python]": {
        "editor.codeActionsOnSave": {
            "source.organizeImports": true
        }
    }
}
```

#### PyCharm

1. Set Python interpreter to `./venv/bin/python`
2. Enable Black formatter
3. Enable isort for imports

## Troubleshooting

### Common Issues

**Virtual environment not activated**
```bash
source venv/bin/activate
```

**Dependencies not installed**
```bash
pip install -r requirements.txt
```

**Pre-commit hooks not running**
```bash
pre-commit install
```

**Configuration file not found**
```bash
cp config/config.example.yaml config/config.yaml
```

**Login output is noisy (HTTP polling spam)**
Set `logging.level` to `WARNING` in `config/config.yaml` or run:
```bash
LOGGING_LEVEL=WARNING python -m src.main login
```

### Getting Help

- Check the [Documentation Index](INDEX.md)
- Review [CI documentation](CI.md) for testing issues
- Open an issue on GitHub
