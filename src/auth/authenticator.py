"""Microsoft Graph authentication using Device Code Flow."""

import logging
from typing import Optional

from azure.identity import DeviceCodeCredential
from msgraph import GraphServiceClient

from src.auth.token_cache import TokenCache
from src.config.settings import AzureSettings

logger = logging.getLogger(__name__)


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
        self._credential: Optional[DeviceCodeCredential] = None
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

    def _create_credential(self) -> DeviceCodeCredential:
        """Create Device Code credential.

        Returns:
            DeviceCodeCredential instance

        Raises:
            AuthenticationError: If client_id is not configured
        """
        if not self.client_id:
            raise AuthenticationError(
                "Azure client_id not configured. Please set it in config/config.yaml "
                "or via AZURE_CLIENT_ID environment variable."
            )

        logger.debug("Creating DeviceCodeCredential")
        return DeviceCodeCredential(
            client_id=self.client_id,
            tenant_id=self.tenant,
        )

    async def authenticate(self) -> GraphServiceClient:
        """Perform device code authentication flow.

        This method will:
        1. Check if valid cached token exists
        2. If not, initiate device code flow (user must visit URL and enter code)
        3. Cache the token for future use
        4. Return authenticated GraphServiceClient

        Returns:
            Authenticated GraphServiceClient instance

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Check if we have a valid cached token
            if self.token_cache and self.token_cache.has_valid_token():
                logger.info("Using cached authentication token")
                # Load cached token into credential
                self._credential = self._create_credential()
            else:
                logger.info("No valid cached token, initiating device code flow")
                self._credential = self._create_credential()

            # Create Graph client with the credential
            self._client = GraphServiceClient(credentials=self._credential, scopes=self.scopes)

            # Test authentication by getting user info
            logger.debug("Testing authentication by fetching user info")
            user = await self._client.me.get()

            if user and user.user_principal_name:
                logger.info(f"Successfully authenticated as {user.user_principal_name}")

                # Cache the token for future use
                if self.token_cache:
                    # Get a token to cache
                    token = await self._credential.get_token(*self.scopes)
                    await self.token_cache.save_token(token.token, token.expires_on, self.scopes)
                    logger.debug("Token cached successfully")
            else:
                raise AuthenticationError("Failed to retrieve user information")

            return self._client

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

        This method will request a new token using the refresh token.

        Raises:
            AuthenticationError: If token refresh fails
        """
        try:
            logger.info("Refreshing authentication token")

            if not self._credential:
                self._credential = self._create_credential()

            # Request new token
            token = await self._credential.get_token(*self.scopes)

            # Update cache
            if self.token_cache:
                await self.token_cache.save_token(token.token, token.expires_on, self.scopes)
                logger.info("Token refreshed successfully")
            else:
                logger.warning("Token refreshed but no cache available to save it")

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
