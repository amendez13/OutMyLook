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
- Handle user commands (login, logout, status, fetch)
- Display authentication status and messages
- Provide interactive prompts and feedback
- Render fetched email data in a readable format

**Key Files**:
- `src/cli/commands.py` - CLI commands using Typer
- `src/cli/__init__.py` - Module exports
- `src/main.py` - Main entry point that invokes the CLI

**Commands**:
- `login` - Authenticate with Microsoft Graph
- `logout` - Clear authentication tokens
- `status` - Check authentication status
- `fetch` - Fetch emails from a mail folder

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
   - TokenCache saves tokens to a local JSON file (~/.outmylook/tokens.json)
   - GraphServiceClient is created with valid credentials

2. **Subsequent Access** (Cached Token):
   - User runs a command requiring authentication
   - TokenCache checks for valid cached token
   - If token exists and not expired, use cached token
   - If token expired, automatically refresh using refresh token
   - Create GraphServiceClient with cached credentials

3. **Token Refresh**:
   - TokenCache detects token expiring within 5 minutes
   - GraphAuthenticator requests new token using refresh token
   - New token saved to cache
   - Application continues without user intervention

4. **Logout**:
   - User runs `python -m src.main logout`
   - TokenCache clears cached tokens
   - User must re-authenticate on next use

### Email Fetch Flow

1. **Fetch Request**:
   - User runs `python -m src.main fetch --folder inbox --limit 25 --skip 0`
   - CLI validates authentication via TokenCache
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
6. **CLI Output**:
   - The CLI renders a table of received time, sender, subject, and flags

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

**Decision**: Store OAuth tokens in a local JSON file (~/.outmylook/tokens.json) with restrictive file permissions (600). Implement automatic token refresh before expiration.

**Consequences**:
- Pro: Users authenticate once, tokens persist across sessions
- Pro: Automatic refresh eliminates re-authentication for expired tokens
- Pro: File permissions (600) protect sensitive tokens
- Pro: Simple JSON format, easy to inspect and debug
- Con: Tokens stored on disk (restricted permissions but still a security consideration)
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

- **Token Caching**: Tokens cached to disk eliminate need for re-authentication, reducing latency for subsequent API calls
- **Automatic Refresh**: Tokens refreshed automatically before expiration (5-minute buffer) to prevent authentication delays
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

- **File Location**: Tokens stored in user home directory (~/.outmylook/tokens.json)
- **File Permissions**: Automatically set to 0o600 (read/write for owner only)
- **Token Refresh**: Refresh tokens used to obtain new access tokens without re-authentication
- **Clear on Logout**: Tokens completely removed from disk on logout

### Best Practices

- **Minimal Scopes**: Request only necessary Microsoft Graph API scopes (Mail.Read, User.Read, offline_access)
- **Token Validation**: Check token expiration before use with 5-minute buffer
- **Error Handling**: Authentication errors caught and reported clearly to users
- **Logging**: Sensitive data (tokens, credentials) never logged

## Future Enhancements

- [ ] Support for additional OAuth flows (Authorization Code, Client Credentials)
- [ ] Token encryption using OS keyring (e.g., keyring library)
- [ ] Multi-account support
- [ ] Token refresh background service
- [ ] Integration with system credential managers (Windows Credential Manager, macOS Keychain)
