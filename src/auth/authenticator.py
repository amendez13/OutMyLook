"""Microsoft Graph authentication using Device Code Flow."""

import asyncio
import logging
from typing import Any, Optional

from azure.core.credentials import AccessToken, TokenCredential
from azure.identity import DeviceCodeCredential
from msgraph import GraphServiceClient

from src.auth.token_cache import TokenCache
from src.config.settings import AzureSettings

logger = logging.getLogger(__name__)


class CachedTokenCredential(TokenCredential):
    """A TokenCredential that uses cached tokens when available.

    This credential checks the token cache first. If a valid token exists,
    it returns that token. Otherwise, it delegates to DeviceCodeCredential
    to perform interactive authentication and caches the result.
    """

    def __init__(
        self,
        client_id: str,
        tenant_id: str,
        token_cache: Optional[TokenCache] = None,
    ):
        """Initialize the CachedTokenCredential.

        Args:
            client_id: Azure AD application (client) ID
            tenant_id: Azure AD tenant ID
            token_cache: Optional token cache for persistent storage
        """
        self._client_id = client_id
        self._tenant_id = tenant_id
        self._token_cache = token_cache
        self._device_code_credential: Optional[DeviceCodeCredential] = None

    def _get_device_code_credential(self) -> DeviceCodeCredential:
        """Get or create the DeviceCodeCredential."""
        if self._device_code_credential is None:
            self._device_code_credential = DeviceCodeCredential(
                client_id=self._client_id,
                tenant_id=self._tenant_id,
            )
        return self._device_code_credential

    def get_token(
        self,
        *scopes: str,
        claims: Optional[str] = None,
        tenant_id: Optional[str] = None,
        enable_cae: bool = False,
        **kwargs: Any,
    ) -> AccessToken:
        """Get an access token for the specified scopes.

        First checks the token cache. If a valid token exists, returns it.
        Otherwise, initiates device code flow and caches the result.

        Args:
            *scopes: The scopes for which the token is requested
            claims: Additional claims required in the token
            tenant_id: Optional tenant to use instead of the configured one
            enable_cae: Enable Continuous Access Evaluation
            **kwargs: Additional keyword arguments

        Returns:
            An AccessToken with the token string and expiration time
        """
        # Check cache first
        if self._token_cache and self._token_cache.has_valid_token():
            logger.info("Using cached authentication token")
            # Load token from cache synchronously
            try:
                token_data = self._token_cache._read_token_file()
                access_token = token_data.get("access_token", "")
                expires_on = token_data.get("expires_on", 0)
                return AccessToken(access_token, expires_on)
            except Exception as e:
                logger.warning(f"Failed to read cached token: {e}, falling back to device code flow")

        # No valid cached token, use device code flow
        logger.info("No valid cached token, initiating device code flow")
        credential = self._get_device_code_credential()
        token = credential.get_token(*scopes, claims=claims, tenant_id=tenant_id, enable_cae=enable_cae, **kwargs)

        # Cache the new token
        if self._token_cache:
            try:
                # Run async save in sync context
                asyncio.get_event_loop().run_until_complete(
                    self._token_cache.save_token(token.token, token.expires_on, list(scopes))
                )
                logger.debug("Token cached successfully")
            except RuntimeError:
                # No event loop running, create one
                asyncio.run(self._token_cache.save_token(token.token, token.expires_on, list(scopes)))
                logger.debug("Token cached successfully")
            except Exception as e:
                logger.warning(f"Failed to cache token: {e}")

        return token

    async def close(self) -> None:
        """Close the credential."""
        if self._device_code_credential:
            self._device_code_credential.close()


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class GraphAuthenticator:
    """Handles OAuth2 authentication with Microsoft Graph using Device Code Flow.

    This authenticator uses the Device Code Flow which is ideal for CLI applications
    and headless environments. Users authenticate by visiting a URL and entering
    a code displayed in the terminal.

    Attributes:
        client_id: Azure AD application (client) ID
        tenant: Azure AD tenant ID or "common" for personal accounts
        scopes: List of Microsoft Graph API permission scopes
        token_cache: Token cache instance for persistent token storage
    """

    def __init__(
        self,
        client_id: str,
        tenant: str = "common",
        scopes: Optional[list[str]] = None,
        token_cache: Optional[TokenCache] = None,
    ):
        """Initialize the GraphAuthenticator.

        Args:
            client_id: Azure AD application (client) ID
            tenant: Azure AD tenant ID or "common" for personal accounts
            scopes: List of Microsoft Graph API scopes
            token_cache: Optional token cache instance
        """
        self.client_id = client_id
        self.tenant = tenant
        self.scopes = scopes or [
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/User.Read",
            "offline_access",
        ]
        self.token_cache = token_cache
        self._credential: Optional[CachedTokenCredential] = None
        self._client: Optional[GraphServiceClient] = None

        logger.debug(f"Initialized GraphAuthenticator with client_id={client_id}, " f"tenant={tenant}, scopes={self.scopes}")

    @classmethod
    def from_settings(cls, azure_settings: AzureSettings, token_cache: Optional[TokenCache] = None) -> "GraphAuthenticator":
        """Create authenticator from Azure settings.

        Args:
            azure_settings: Azure configuration settings
            token_cache: Optional token cache instance

        Returns:
            GraphAuthenticator instance
        """
        return cls(
            client_id=azure_settings.client_id,
            tenant=azure_settings.tenant,
            scopes=azure_settings.scopes,
            token_cache=token_cache,
        )

    def _create_credential(self) -> CachedTokenCredential:
        """Create a credential that uses cached tokens when available.

        Returns:
            CachedTokenCredential instance

        Raises:
            AuthenticationError: If client_id is not configured
        """
        if not self.client_id:
            raise AuthenticationError(
                "Azure client_id not configured. Please set it in config/config.yaml "
                "or via AZURE_CLIENT_ID environment variable."
            )

        logger.debug("Creating CachedTokenCredential")
        return CachedTokenCredential(
            client_id=self.client_id,
            tenant_id=self.tenant,
            token_cache=self.token_cache,
        )

    async def authenticate(self) -> GraphServiceClient:
        """Perform device code authentication flow.

        This method will:
        1. Check if valid cached token exists (handled by CachedTokenCredential)
        2. If not, initiate device code flow (user must visit URL and enter code)
        3. Cache the token for future use (handled by CachedTokenCredential)
        4. Return authenticated GraphServiceClient

        Returns:
            Authenticated GraphServiceClient instance

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Create credential that handles caching internally
            self._credential = self._create_credential()

            # Create Graph client with the credential
            self._client = GraphServiceClient(credentials=self._credential, scopes=self.scopes)

            # Test authentication by getting user info
            # This will trigger the credential's get_token which checks cache first
            logger.debug("Testing authentication by fetching user info")
            user = await self._client.me.get()

            if user and user.user_principal_name:
                logger.info(f"Successfully authenticated as {user.user_principal_name}")
            else:
                raise AuthenticationError("Failed to retrieve user information")

            return self._client

        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise AuthenticationError(f"Authentication failed: {e}") from e

    def is_authenticated(self) -> bool:
        """Check if valid cached token exists.

        Returns:
            True if valid cached token exists, False otherwise
        """
        if not self.token_cache:
            return False
        return self.token_cache.has_valid_token()

    async def get_client(self) -> GraphServiceClient:
        """Get authenticated Graph client.

        If not already authenticated, this will initiate the authentication flow.

        Returns:
            Authenticated GraphServiceClient instance

        Raises:
            AuthenticationError: If authentication fails
        """
        if self._client is None:
            return await self.authenticate()
        return self._client

    async def refresh_token(self) -> None:
        """Refresh expired token.

        This forces a new device code flow to get a fresh token.
        The CachedTokenCredential will cache the new token automatically.

        Raises:
            AuthenticationError: If token refresh fails
        """
        try:
            logger.info("Refreshing authentication token")

            # Clear the cache to force a fresh authentication
            if self.token_cache:
                await self.token_cache.clear()

            # Create a fresh credential and get a new token
            self._credential = self._create_credential()

            # Request new token - this will trigger device code flow
            # since cache was cleared
            token = self._credential.get_token(*self.scopes)

            logger.info(f"Token refreshed successfully, expires at {token.expires_on}")

        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise AuthenticationError(f"Token refresh failed: {e}") from e

    async def logout(self) -> None:
        """Logout and clear cached tokens.

        This will remove cached tokens, requiring re-authentication on next use.
        """
        logger.info("Logging out and clearing cached tokens")

        if self.token_cache:
            await self.token_cache.clear()

        self._credential = None
        self._client = None
        logger.info("Logout completed")
