# Architecture Documentation

This document describes the technical architecture of OutMyLook.

## Overview

OutMyLook is a Python application for managing Microsoft Outlook emails using the Microsoft Graph API. The application follows a modular architecture with separation of concerns between authentication, data access, storage, and user interface layers.

## System Components

### Component Diagram

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────┐
│     CLI      │────▶│  Authentication  │────▶│   Graph     │
│  (Typer)     │     │    (OAuth2)      │     │     API     │
└──────────────┘     └──────────────────┘     └─────────────┘
       │                      │
       ▼                      ▼
┌──────────────┐     ┌──────────────────┐
│ Email Client │     │   Token Cache    │
│ + Models     │     │   (Local JSON)   │
└──────────────┘     └──────────────────┘
       │
       ▼
┌──────────────┐
│  Database    │
│  (SQLite)    │
└──────────────┘
```

### Authentication Module

**Purpose**: Handles OAuth2 authentication with Microsoft Graph API using Device Code Flow

**Responsibilities**:
- Authenticate users with Microsoft accounts via Device Code Flow
- Manage OAuth2 tokens with automatic refresh
- Cache tokens securely for session persistence
- Handle authentication errors gracefully

**Key Files**:
- `src/auth/authenticator.py` - GraphAuthenticator class for OAuth2 authentication
- `src/auth/token_cache.py` - TokenCache class for persistent token storage
- `src/auth/__init__.py` - Module exports

**Key Classes**:

1. **GraphAuthenticator**
   - `authenticate()` - Performs Device Code authentication flow
   - `refresh_token()` - Refreshes expired tokens
   - `is_authenticated()` - Checks authentication status
   - `logout()` - Clears cached tokens

2. **TokenCache**
   - `save_token()` - Saves tokens to a local JSON file
   - `load_token()` - Loads tokens from cache
   - `has_valid_token()` - Validates token expiration
   - `clear()` - Removes cached tokens

### CLI Module

**Purpose**: Provides command-line interface for user interactions

**Responsibilities**:
- Handle user commands (login, logout, status, fetch, list, export, download)
- Display authentication status and messages
- Provide interactive prompts and feedback
- Render fetched/stored email data in a readable format
- Export stored data to JSON/CSV

**Key Files**:
- `src/cli/commands.py` - CLI commands using Typer
- `src/cli/formatters.py` - Rich formatters for tables and status output
- `src/cli/exporters.py` - JSON/CSV export helpers
- `src/cli/__init__.py` - Module exports
- `src/main.py` - Main entry point that invokes the CLI

**Commands**:
- `login` - Authenticate with Microsoft Graph
- `logout` - Clear authentication tokens
- `status` - Check authentication status
- `fetch` - Fetch emails from a mail folder
- `list` - Query stored emails in the local database
- `export` - Export stored emails to JSON or CSV
- `download` - Download attachments for stored emails

### Email Module

**Purpose**: Wrap Microsoft Graph SDK calls and map message data to typed models.

**Responsibilities**:
- Resolve folder names or IDs to a Graph folder identifier
- Fetch message lists with pagination
- Map Graph SDK message payloads to Pydantic models

**Key Files**:
- `src/email/client.py` - EmailClient wrapper around GraphServiceClient
- `src/email/models.py` - Pydantic models for email and folder data

**Key Classes**:

1. **EmailClient**
   - `list_emails()` - Fetch messages for a folder with `limit` and `skip`
   - `get_email()` - Fetch a single message by ID
   - `list_folders()` - Fetch available mail folders

2. **Email / EmailAddress / MailFolder**
   - Normalize Graph fields (e.g., `receivedDateTime`, `bodyPreview`)
   - Validate required values and provide consistent typing

### Attachment Module

**Purpose**: Download and track message attachments.

**Responsibilities**:
- List and download attachments via Microsoft Graph
- Store files in the configured attachments directory
- Persist attachment metadata and download status

**Key Files**:
- `src/attachments/handler.py` - AttachmentHandler for listing and downloads
- `src/attachments/models.py` - Attachment metadata model

**Key Classes**:

1. **AttachmentHandler**
   - `list_attachments()` - List attachment metadata
   - `download_attachment()` - Download a single attachment
   - `download_all_for_email()` - Download all attachments for an email

### Database Module

**Purpose**: Persist fetched emails for local querying and historical access.

**Responsibilities**:
- Define SQLAlchemy ORM models for emails and attachments
- Initialize schema automatically for SQLite databases
- Provide repository methods for saving, deduplication, and search
- Support Alembic migrations for schema evolution

**Key Files**:
- `src/database/models.py` - ORM models and indexes
- `src/database/repository.py` - Async session helpers and repository
- `src/database/migrations/` - Alembic migration scripts
- `alembic.ini` - Alembic configuration

**Key Classes**:

1. **EmailRepository**
   - `save()` / `save_many()` - Insert or update emails
   - `get_by_id()` - Fetch a stored email by Graph ID
   - `list_all()` - List stored emails with pagination
   - `search()` - Filter by sender, subject, or date range

### Configuration Module

**Purpose**: Manages application configuration and settings

**Responsibilities**:
- Load configuration from YAML files and environment variables
- Validate configuration settings
- Provide typed access to configuration

**Key Files**:
- `src/config/settings.py` - Settings classes using Pydantic

## Data Flow

### Authentication Flow

1. **Initial Authentication** (Device Code Flow):
   - User runs `python -m src.main login`
   - GraphAuthenticator creates DeviceCodeCredential
   - Azure AD provides URL and device code
   - User visits URL and enters code in browser
   - User authenticates with Microsoft account
   - Azure AD returns access and refresh tokens
   - MSAL stores tokens in its persistent cache
   - OutMyLook persists a non-secret auth record to `~/.outmylook/auth_record.json`
   - GraphServiceClient is created with valid credentials

2. **Subsequent Access** (Cached Token):
   - User runs a command requiring authentication
   - DeviceCodeCredential loads the auth record
   - MSAL silently acquires or refreshes tokens
   - GraphServiceClient is created with cached credentials
   - TokenCache writes token metadata to `storage.token_file` for status output

3. **Token Refresh**:
   - MSAL handles refresh tokens automatically when access tokens expire
   - Application continues without user intervention

4. **Logout**:
   - User runs `python -m src.main logout`
   - TokenCache clears token metadata
   - Auth record is removed from disk
   - User must re-authenticate on next use

### Email Fetch Flow

1. **Fetch Request**:
   - User runs `python -m src.main fetch --folder inbox --limit 25 --skip 0`
   - CLI asks GraphAuthenticator for a GraphServiceClient (refresh tokens are used if available)
2. **Client Initialization**:
   - GraphAuthenticator returns a GraphServiceClient instance
   - EmailClient wraps the GraphServiceClient
3. **Folder Resolution**:
   - EmailClient resolves a well-known folder name or display name to a folder ID
4. **Graph API Call**:
   - EmailClient requests messages with `top` and `skip` parameters
   - The request selects only needed fields (subject, sender, receivedDateTime, etc.)
5. **Model Mapping**:
   - Email models normalize Graph fields into typed data
   - Invalid messages are skipped with a warning
6. **Persistence**:
   - EmailRepository bulk-saves emails with deduplication by message ID
   - Existing rows are updated to reflect new metadata
7. **CLI Output**:
   - The CLI renders a table of received time, sender, subject, and flags

### Attachment Download Flow

1. **Download Request**:
   - User runs `python -m src.main download <email_id>` or a filter-based command
2. **Attachment Listing**:
   - AttachmentHandler lists attachments for the email
3. **Download**:
   - Files are downloaded to `storage.attachments_dir/<email_id>/`
   - Filename conflicts are resolved with numeric suffixes
4. **Metadata Update**:
   - AttachmentRepository stores metadata and marks downloads with local paths

## Design Decisions

### Decision 1: Device Code Flow for Authentication

**Context**: CLI applications cannot open browser redirects like web applications. Need a user-friendly way to authenticate without embedded browsers or localhost servers.

**Decision**: Use Device Code Flow from Azure Identity SDK. This flow displays a URL and code for users to enter in their browser, making it ideal for CLI tools and headless environments.

**Consequences**:
- Pro: Simple user experience - copy code, visit URL, paste code
- Pro: Works in all environments (SSH, containers, headless)
- Pro: No need for localhost redirect handling
- Pro: Official Microsoft recommendation for CLI apps
- Con: Requires manual browser interaction (cannot be fully automated)
- Con: User must have browser access

### Decision 2: Persistent Token Caching

**Context**: Requiring re-authentication on every command execution would severely degrade user experience. Need secure, persistent token storage.

**Decision**: Use MSAL persistent caching and store a non-secret auth record locally
(`~/.outmylook/auth_record.json`). Keep `tokens.json` for status output only.

**Consequences**:
- Pro: Users authenticate once, tokens persist across sessions
- Pro: Automatic refresh eliminates re-authentication for expired tokens
- Pro: Auth record is non-secret and easy to clear
- Pro: Token metadata JSON remains useful for status reporting
- Con: MSAL cache still stores tokens on disk (OS-managed)
- Con: Tokens not shared across machines (each machine needs separate auth)

### Decision 3: Async/Await for API Calls

**Context**: Microsoft Graph SDK uses async/await pattern. Need consistent async handling throughout authentication module.

**Decision**: Use async/await for all authentication and token operations. Use asyncio.to_thread() for file I/O to maintain async interface while avoiding blocking operations.

**Consequences**:
- Pro: Consistent with Microsoft Graph SDK patterns
- Pro: Future-proof for concurrent operations
- Pro: Non-blocking file I/O operations
- Con: Slightly more complex code with async/await syntax
- Con: Requires asyncio.run() wrapper in CLI commands

## Performance Considerations

- **Token Caching**: MSAL persistent cache enables silent token reuse across CLI runs
- **Automatic Refresh**: Tokens refreshed automatically when access tokens expire
- **Async I/O**: Non-blocking file operations prevent UI freezes during token read/write operations
- **Minimal Dependencies**: Using official Microsoft libraries reduces overhead and ensures optimal performance

## Security Considerations

### Authentication Security

- **OAuth2 Device Code Flow**: Industry-standard authentication, no passwords stored locally
- **Token Encryption**: Tokens stored with restrictive file permissions (600) - owner read/write only
- **Automatic Expiration**: Tokens expire and refresh automatically, limiting exposure window
- **No Credentials Storage**: Client ID is the only credential stored, client secret not required for Device Code Flow
- **HTTPS Only**: All communication with Microsoft Graph API over HTTPS

### Token Storage

- **Auth Record**: Stored at `~/.outmylook/auth_record.json` (non-secret account metadata)
- **MSAL Cache**: Stored via MSAL/azure-identity persistent cache (OS-managed)
- **Token Metadata**: `~/.outmylook/tokens.json` is informational for status output
- **Clear on Logout**: Auth record and token metadata removed from disk on logout

### Best Practices

- **Minimal Scopes**: Request only necessary Microsoft Graph API scopes (Mail.Read, User.Read)
- **Token Validation**: Check token expiration before use with 5-minute buffer
- **Error Handling**: Authentication errors caught and reported clearly to users
- **Logging**: Sensitive data (tokens, credentials) never logged

## Future Enhancements

- [ ] Support for additional OAuth flows (Authorization Code, Client Credentials)
- [ ] Token encryption using OS keyring (e.g., keyring library)
- [ ] Multi-account support
- [ ] Token refresh background service
- [ ] Integration with system credential managers (Windows Credential Manager, macOS Keychain)
