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

## Quick Start

### Prerequisites

- Python 3.10 or higher
- pip (Python package installer)
- Microsoft account (@outlook.com, @hotmail.com, @live.com, or organizational account)
- Azure AD application registration (see [Setup Guide](docs/SETUP.md) for details)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/OutMyLook.git
cd OutMyLook
```

2. Create and activate virtual environment:
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

### Usage

#### Authentication

First, authenticate with your Microsoft account:

```bash
# Login with Device Code Flow
python -m src.main login

# Check authentication status
python -m src.main status

# Logout (clear cached tokens)
python -m src.main logout
```

The login command will display a URL and device code. Visit the URL in your browser and enter the code to complete authentication. Your tokens will be cached securely for future use.

#### Email Management

```bash
python -m src.main fetch --limit 10 --folder inbox  # Fetch emails
python -m src.main list                              # List stored emails
python -m src.main export emails.json --format json  # Export emails
python -m src.main download <email_id>               # Download attachments
```

Use `--verbose` for detailed logs or `--quiet` for summary-only output.

See `docs/USAGE.md` for a full usage guide, including configuration tips, folder selection, pagination,
local database querying/export, and attachment downloads.

## Configuration

Configuration is stored in `config/config.yaml`. See `config/config.example.yaml` for all available options.

```yaml
# Azure AD Application Settings
azure:
  # Your Azure AD application (client) ID
  client_id: "your-azure-app-client-id"

  # Tenant ID - use "common" for personal Microsoft accounts
  tenant: "common"

  # Microsoft Graph API scopes
  scopes:
    - "https://graph.microsoft.com/Mail.Read"
    - "https://graph.microsoft.com/User.Read"
    - "offline_access"

# Database Configuration
database:
  url: "sqlite:///~/.outmylook/emails.db"

# Storage Settings
storage:
  attachments_dir: "~/.outmylook/attachments"
  token_file: "~/.outmylook/tokens.json"

# Logging Configuration
logging:
  level: "INFO"
```

**Important**: You need to register an Azure AD application to get your `client_id`. See [Setup Guide](docs/SETUP.md) for detailed instructions.
For database configuration and migrations, see [Database Guide](docs/DATABASE.md).

## Project Structure

```
OutMyLook/
├── .github/workflows/    # CI/CD configuration
├── .claude/              # Claude Code configuration
├── config/               # Configuration files
├── docs/                 # Documentation
├── src/       # Source code
├── tests/         # Test files
├── CLAUDE.md             # AI assistant guidance
├── README.md             # This file
├── pyproject.toml        # Tool configuration
└── requirements.txt      # Dependencies
```

## Development

### Setup Development Environment

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
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
- [CI Documentation](docs/CI.md) - CI/CD pipeline details

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit your changes (`git commit -m 'feat: add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

[Choose your license]

## Acknowledgments

- [Acknowledgment 1]
- [Acknowledgment 2]
