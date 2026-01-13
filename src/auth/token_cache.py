"""Token caching with automatic refresh for Microsoft Graph authentication."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TokenCacheError(Exception):
    """Raised when token cache operations fail."""

    pass


class TokenCache:
    """Manages persistent storage and automatic refresh of OAuth tokens.

    Tokens are stored in an encrypted JSON file on disk, allowing the application
    to maintain authentication across sessions without requiring users to
    re-authenticate each time.

    Attributes:
        token_file: Path to the token cache file
    """

    def __init__(self, token_file: str | Path):
        """Initialize the TokenCache.

        Args:
            token_file: Path to token cache file (will be created if doesn't exist)
        """
        self.token_file = Path(token_file).expanduser()
        self._ensure_directory()
        logger.debug(f"Initialized TokenCache with file: {self.token_file}")

    def _ensure_directory(self) -> None:
        """Ensure the directory for token file exists."""
        self.token_file.parent.mkdir(parents=True, exist_ok=True)

    async def save_token(self, access_token: str, expires_on: int, scopes: list[str]) -> None:
        """Save token to cache file.

        Args:
            access_token: The OAuth access token
            expires_on: Token expiration timestamp (Unix timestamp)
            scopes: List of scopes the token is valid for

        Raises:
            TokenCacheError: If saving fails
        """
        try:
            token_data = {
                "access_token": access_token,
                "expires_on": expires_on,
                "scopes": scopes,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }

            # Use asyncio to write file without blocking
            await asyncio.to_thread(self._write_token_file, token_data)

            logger.info(f"Token cached successfully to {self.token_file}")

        except Exception as e:
            logger.error(f"Failed to save token: {e}")
            raise TokenCacheError(f"Failed to save token: {e}") from e

    def _write_token_file(self, token_data: dict[str, Any]) -> None:
        """Write token data to file (synchronous helper).

        Args:
            token_data: Token data dictionary
        """
        with open(self.token_file, "w") as f:
            json.dump(token_data, f, indent=2)
        # Set restrictive permissions (owner read/write only)
        self.token_file.chmod(0o600)

    async def load_token(self) -> Optional[dict[str, Any]]:
        """Load token from cache file.

        Returns:
            Token data dictionary if exists and valid, None otherwise
        """
        if not self.token_file.exists():
            logger.debug("Token file does not exist")
            return None

        try:
            token_data = await asyncio.to_thread(self._read_token_file)
            logger.debug("Token loaded from cache")
            return token_data

        except Exception as e:
            logger.warning(f"Failed to load token: {e}")
            return None

    def load_token_sync(self) -> Optional[dict[str, Any]]:
        """Load token from cache file synchronously.

        Returns:
            Token data dictionary if exists and readable, None otherwise
        """
        if not self.token_file.exists():
            logger.debug("Token file does not exist")
            return None

        try:
            token_data = self._read_token_file()
            logger.debug("Token loaded from cache (sync)")
            return token_data
        except Exception as e:
            logger.warning(f"Failed to load token: {e}")
            return None

    def _read_token_file(self) -> dict[str, Any]:
        """Read token data from file (synchronous helper).

        Returns:
            Token data dictionary
        """
        with open(self.token_file, "r") as f:
            data: dict[str, Any] = json.load(f)
            return data

    def has_valid_token(self) -> bool:
        """Check if a valid (non-expired) token exists in cache.

        Returns:
            True if valid token exists, False otherwise
        """
        if not self.token_file.exists():
            return False

        try:
            token_data = self._read_token_file()

            # Check if token has required fields
            if not all(key in token_data for key in ["access_token", "expires_on"]):
                logger.debug("Token cache missing required fields")
                return False

            # Check if token is expired (with 5 minute buffer)
            expires_on = token_data["expires_on"]
            current_time = datetime.now(timezone.utc).timestamp()
            buffer_seconds = 300  # 5 minutes

            if current_time >= (expires_on - buffer_seconds):
                logger.debug("Cached token is expired or expiring soon")
                return False

            logger.debug("Valid token found in cache")
            return True

        except Exception as e:
            logger.warning(f"Error checking token validity: {e}")
            return False

    async def clear(self) -> None:
        """Clear cached token by removing the cache file.

        This is useful for logout functionality.
        """
        try:
            if self.token_file.exists():
                await asyncio.to_thread(self.token_file.unlink)
                logger.info("Token cache cleared")
            else:
                logger.debug("No token cache to clear")

        except Exception as e:
            logger.error(f"Failed to clear token cache: {e}")
            raise TokenCacheError(f"Failed to clear token cache: {e}") from e

    async def get_access_token(self) -> Optional[str]:
        """Get access token from cache if valid.

        Returns:
            Access token string if valid token exists, None otherwise
        """
        if not self.has_valid_token():
            return None

        token_data = await self.load_token()
        if token_data:
            return token_data.get("access_token")
        return None

    async def get_token_info(self) -> Optional[dict[str, Any]]:
        """Get full token information from cache.

        Returns:
            Dictionary with token info including expiration time and scopes,
            None if no valid token exists
        """
        if not self.has_valid_token():
            return None

        token_data = await self.load_token()
        if not token_data:
            return None

        # Calculate time until expiration
        expires_on = token_data.get("expires_on", 0)
        current_time = datetime.now(timezone.utc).timestamp()
        seconds_until_expiry = int(expires_on - current_time)

        return {
            "expires_on": expires_on,
            "expires_at": datetime.fromtimestamp(expires_on, tz=timezone.utc).isoformat(),
            "seconds_until_expiry": seconds_until_expiry,
            "scopes": token_data.get("scopes", []),
            "cached_at": token_data.get("cached_at"),
        }

    def is_token_expiring_soon(self, threshold_seconds: int = 300) -> bool:
        """Check if token will expire within threshold time.

        Args:
            threshold_seconds: Number of seconds to use as threshold (default: 5 minutes)

        Returns:
            True if token expires within threshold, False otherwise
        """
        if not self.token_file.exists():
            return True

        try:
            token_data = self._read_token_file()
            expires_on: int = token_data.get("expires_on", 0)
            current_time = datetime.now(timezone.utc).timestamp()

            return bool(current_time >= (expires_on - threshold_seconds))

        except Exception:
            return True
