# Documentation Index

Welcome to the OutMyLook documentation. This index provides easy access to all documentation in this repository.

## Quick Links

**For Users:**
- [Getting Started](#getting-started) - Start here if you're new
- [Setup Guide](#setup-guides) - Configure your environment
- [Usage Guide](#usage) - CLI usage and examples
- [Database Guide](#database) - Persistent storage details
- [Example Scripts](#examples) - Practical end-to-end scripts

**For Developers:**
- [Architecture](#architecture) - Technical design and implementation details
- [Developer Guide](#developer-resources) - Contributing and development workflow
- [API Reference](#api-reference) - Python module overview

---

## Getting Started

**[README.md](../README.md)**
- Project overview and features
- Quick start guide
- Installation instructions
- Basic configuration
- Usage examples
- Troubleshooting common issues

---

## Setup Guides

**[SETUP.md](SETUP.md)**
- Prerequisites and system requirements
- Step-by-step installation guide
- Configuration options
- Verification steps
- Troubleshooting

---

## Usage

**[USAGE.md](USAGE.md)**
- Authentication flow (login, status, logout)
- Fetching email with pagination and folder selection
- Listing stored emails and exporting JSON/CSV
- Downloading attachments and storage location
- Global output controls (verbose/quiet), configuration notes, and troubleshooting

---

## Database

**[DATABASE.md](DATABASE.md)**
- Database setup and configuration
- Schema overview and persistence flow
- Migrations and troubleshooting

---

## Architecture

**[ARCHITECTURE.md](ARCHITECTURE.md)**
- System architecture overview
- Component design
- Design decisions and trade-offs
- Performance considerations
- Security implications

OutMyLook is organized around an authentication layer (Device Code Flow), a Graph
client wrapper for email operations, a local persistence layer using SQLAlchemy,
and a CLI that wires these layers together for end users.

---

## API Reference

**[API.md](API.md)**
- Overview of public Python modules and classes
- Suggested integration points for scripting

---

## Examples

**[examples/](../examples/)**
- [fetch_recent.py](../examples/fetch_recent.py) - Fetch and display recent emails
- [download_attachments.py](../examples/download_attachments.py) - Download attachments from filtered emails
- [export_to_csv.py](../examples/export_to_csv.py) - Export stored emails to CSV

---

## Developer Resources

**[CLAUDE.md](../CLAUDE.md)**
- Project overview for AI assistants
- Technology stack details
- Core workflow and key components
- Development commands and setup
- Common development tasks

**[CI.md](CI.md)**
- Continuous Integration (CI) pipeline documentation
- GitHub Actions workflow details
- Code quality and testing automation
- Local development workflow
- Running CI checks locally
- Troubleshooting CI failures

---

## Project Status

**Current Phase:** Phase 8 - Testing & Documentation
- Integration tests with mocked Graph API
- Documentation and examples refresh

**Next Phase:** TBD

**Future:** TBD

---

## Quick Reference

| Document | Purpose | Audience |
|----------|---------|----------|
| [README.md](../README.md) | Getting started, installation, usage | All users |
| [SETUP.md](SETUP.md) | Environment configuration | All users |
| [DATABASE.md](DATABASE.md) | Database storage and migrations | All users |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical architecture and design | Developers |
| [API.md](API.md) | Python module overview | Developers |
| [CI.md](CI.md) | CI/CD pipeline and development workflow | Developers |
| [CLAUDE.md](../CLAUDE.md) | AI assistant guidance | Claude Code |

---

## Task Management

**[planning/TASK_MANAGEMENT.md](planning/TASK_MANAGEMENT.md)**
- Development phases and milestones
- Task tracking and prioritization
- Progress monitoring
