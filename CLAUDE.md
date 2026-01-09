# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python project

**Core workflow**: [Describe the main workflow of your application]

## Constraints and Best Practices

* This project is documentation-driven. Before starting work, read:
  * README.md
  * docs/INDEX.md
* After finishing any task, update relevant documentation given changes in codebase.
* Pre-commit checks must pass before committing. If pre-commit doesn't run, investigate and fix.
* Branch naming: `feature/description`, `fix/description`, `docs/description`
* Commit messages: Use conventional commits (feat:, fix:, docs:, refactor:, test:, chore:)

## Architecture

### Technology Stack
- **Python**: 3.10+
- [Add your main dependencies here]

### Key Components
1. **Component 1**:
   - Description and purpose
   - Key implementation details

2. **Component 2**:
   - Description and purpose
   - Key implementation details

### Processing Strategy
- [Describe your main processing approach]
- Error handling and recovery
- Logging and monitoring

## Development Commands

> **Important**: Always activate the virtual environment before running any commands. You should see `(venv)` in your terminal prompt when it's active. Use `source venv/bin/activate` on macOS/Linux or `venv\Scripts\activate` on Windows.

### Initial Setup

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Copy and configure settings
cp config/config.example.yaml config/config.yaml
# Edit config/config.yaml with your settings
```

### Running Tests

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Run all tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_main.py
```

### Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Update dependencies
pip install --upgrade -r requirements.txt

# Run linting
black src/
isort src/
flake8 src/
mypy src/

# Run security checks
bandit -r src/ -ll

# Deactivate virtual environment when done
deactivate
```

### Running the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run main application
python -m src.main
```
