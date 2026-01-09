# Python Project Template Usage Guide

This template provides a complete Python project setup with CI/CD, quality tools, documentation, and Claude AI configuration.

## Quick Start

### Option 1: Interactive Setup (Recommended)

```bash
# Copy template to your new project location
cp -r /path/to/python-project-template ~/projects/my-new-project

# Navigate to the new project
cd ~/projects/my-new-project

# Run the interactive setup script
python setup_template.py
```

The script will prompt you for:
- Project name and description
- GitHub owner/organization
- Python version requirements
- Code quality settings (line length, complexity, coverage)
- Directory names

### Option 2: Manual Setup

If you prefer to configure manually:

1. Copy the template directory
2. Find and replace all `{{VARIABLE_NAME}}` placeholders in the files
3. Rename `src/` and `tests/` directories if needed
4. Initialize git and install pre-commit hooks

## Template Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `{{PROJECT_NAME}}` | Project name (repository and package) | `my-python-project` |
| `{{PROJECT_DESCRIPTION}}` | Short one-line description | `A Python project` |
| `{{GITHUB_OWNER}}` | GitHub username or organization | `your-username` |
| `{{MIN_PYTHON_VERSION}}` | Minimum Python version | `3.10` |
| `{{PYTHON_VERSIONS}}` | CI matrix versions (comma-separated) | `3.10, 3.11, 3.12` |
| `{{MAX_LINE_LENGTH}}` | Maximum code line length | `127` |
| `{{MAX_COMPLEXITY}}` | Maximum cyclomatic complexity | `10` |
| `{{COVERAGE_THRESHOLD}}` | Minimum test coverage percentage | `95` |
| `{{SOURCE_DIR}}` | Source code directory name | `src` |
| `{{TEST_DIR}}` | Test directory name | `tests` |
| `{{MAIN_BRANCH}}` | Main branch name | `main` |
| `{{DEV_BRANCH}}` | Development branch name | `develop` |

## Template Structure

```
python-project-template/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                 # Main CI pipeline
│   │   ├── claude.yml             # Claude Code automation
│   │   └── claude-code-review.yml # AI code review
│   └── dependabot.yml             # Dependency updates
├── .claude/
│   └── settings.local.json        # Claude Code permissions
├── config/
│   └── config.example.yaml        # Configuration template
├── docs/
│   ├── INDEX.md                   # Documentation hub
│   ├── SETUP.md                   # Installation guide
│   ├── ARCHITECTURE.md            # Technical design
│   ├── CI.md                      # CI/CD documentation
│   ├── BRANCH_PROTECTION.md       # Branch protection documentation
│   └── planning/
│       └── TASK_MANAGEMENT.md     # Task tracking
├── scripts/
│   └── github/
│       ├── branch-protection-config.json  # Protection rules config
│       └── setup-branch-protection.sh     # Setup script
├── src/                           # Source code
│   ├── __init__.py
│   └── main.py
├── tests/                         # Test files
│   ├── __init__.py
│   ├── conftest.py
│   └── test_main.py
├── CLAUDE.md                      # AI assistant guidance
├── README.md                      # Project overview
├── TEMPLATE_USAGE.md              # This file
├── pyproject.toml                 # Tool configuration
├── .pre-commit-config.yaml        # Pre-commit hooks
├── .flake8                        # Flake8 config
├── .pylintrc                      # Pylint config
├── .gitignore                     # Git exclusions
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Development dependencies
└── setup_template.py              # Interactive setup script
```

## What's Included

### CI/CD Pipeline (`.github/workflows/ci.yml`)

- **Lint job**: Black, isort, flake8, mypy
- **Test job**: pytest across Python 3.10, 3.11, 3.12
- **Coverage job**: Enforces coverage threshold with HTML reports
- **Security job**: bandit and pip-audit scanning
- **Config validation**: YAML and Python syntax checks

### Claude AI Workflows (Optional)

- **claude.yml**: Automation triggered by `@claude` mentions in issues/PRs
- **claude-code-review.yml**: Code review via `/claude-review` comment

> **Note**: These require a `CLAUDE_CODE_OAUTH_TOKEN` secret in your repository.

### Pre-commit Hooks

9 hooks configured:
1. Black (code formatting)
2. isort (import sorting)
3. flake8 (linting)
4. mypy (type checking)
5. bandit (security scanning)
6. pip-audit (dependency vulnerabilities)
7. trailing-whitespace
8. end-of-file-fixer
9. check-yaml

### Branch Protection (`scripts/github/`)

Automated branch protection configuration:

- **Required status checks**: All CI jobs must pass
- **Linear history**: No merge commits (squash or rebase only)
- **Conversation resolution**: All review comments must be resolved
- **Force push protection**: Prevents accidental history overwrites
- **Deletion protection**: Prevents accidental branch deletion

Setup via `setup_template.py` or manually:
```bash
./scripts/github/setup-branch-protection.sh
```

See `docs/BRANCH_PROTECTION.md` for full documentation.

### Documentation Structure

- `CLAUDE.md` - AI assistant guidance for Claude Code
- `README.md` - User-facing project documentation
- `docs/INDEX.md` - Central documentation hub
- `docs/CI.md` - CI/CD pipeline documentation
- `docs/SETUP.md` - Installation and configuration guide
- `docs/ARCHITECTURE.md` - Technical architecture (placeholder)
- `docs/BRANCH_PROTECTION.md` - Branch protection rules documentation
- `docs/planning/TASK_MANAGEMENT.md` - Development task tracking

## Post-Setup Steps

After running `setup_template.py`:

1. **Install dependencies**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements-dev.txt
   ```

2. **Verify setup**:
   ```bash
   # Run tests
   pytest

   # Run pre-commit hooks
   pre-commit run --all-files
   ```

3. **Configure GitHub** (if using Claude workflows):
   - Add `CLAUDE_CODE_OAUTH_TOKEN` secret to repository
   - Enable GitHub Actions

4. **Start developing**:
   - Add your code to `src/`
   - Add tests to `tests/`
   - Update documentation as needed

## Customization

### Removing Claude Workflows

If you don't use Claude Code, delete:
- `.github/workflows/claude.yml`
- `.github/workflows/claude-code-review.yml`
- `.claude/` directory

Update `.github/dependabot.yml` to remove the Claude-specific reviewer.

### Adjusting Quality Settings

Edit these files to customize quality rules:
- `pyproject.toml` - Black, isort, pytest, mypy, coverage
- `.flake8` - Flake8 rules
- `.pylintrc` - Pylint rules
- `.pre-commit-config.yaml` - Hook versions and arguments

### Adding Dependencies

1. Add to `requirements.txt` (production)
2. Add to `requirements-dev.txt` (development only)
3. Update `pyproject.toml` if adding type stubs

## Troubleshooting

### Pre-commit hooks fail

```bash
# Update hooks to latest versions
pre-commit autoupdate

# Clear cache and retry
pre-commit clean
pre-commit run --all-files
```

### CI fails on coverage

- Check `htmlcov/index.html` for uncovered lines
- Add tests or use `# pragma: no cover` sparingly
- Adjust `{{COVERAGE_THRESHOLD}}` if needed

### Type checking errors

- Add type hints to function signatures
- Install type stubs: `pip install types-<package>`
- Use `# type: ignore` with explanation for edge cases

## License

This template is provided as-is. Choose an appropriate license for your project.
