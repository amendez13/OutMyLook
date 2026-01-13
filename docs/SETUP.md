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

### 5. Configure the Application

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

### 6. Database Setup (Optional)

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

### 7. Verify Installation

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

### Getting Help

- Check the [Documentation Index](INDEX.md)
- Review [CI documentation](CI.md) for testing issues
- Open an issue on GitHub
