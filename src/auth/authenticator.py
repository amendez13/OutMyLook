"""Microsoft Graph authentication using Device Code Flow."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from azure.core.credentials import AccessToken, TokenCredential
from azure.identity import AuthenticationRecord, DeviceCodeCredential, TokenCachePersistenceOptions
from msgraph import GraphServiceClient

from src.auth.token_cache import TokenCache
from src.config.settings import AzureSettings

logger = logging.getLogger(__name__)


def _refuse_device_code(verification_uri: str, user_code: str, expires_on: object) -> None:
    """Log the device code and stop. Headless timers cannot wait for a browser."""
    del expires_on
    logger.error(
        "Authentication requires interaction. Open %s and enter code %s.",
        verification_uri,
        user_code,
    )
    raise AuthenticationError("Authentication requires interaction. " f"Open {verification_uri} and enter code {user_code}.")


class CachedTokenCredential(TokenCredential):
    """A TokenCredential that uses Azure SDK's persistent token cache.

    This credential uses Azure Identity SDK's built-in token cache persistence,
    which stores both access tokens and refresh tokens. This enables:
    - Silent token refresh using refresh tokens (no user interaction)
    - Persistent authentication across sessions
    - Automatic token refresh when access token expires

    The credential only triggers device code flow when:
    - No cached tokens exist, or
    - The refresh token has expired or been revoked
    """

    def __init__(
        self,
        client_id: str,
        tenant_id: str,
        token_cache: Optional[TokenCache] = None,
        cache_dir: Optional[Path] = None,
        auth_record_file: Optional[Path] = None,
        prompt_callback: Optional[Callable[..., None]] = None,
    ):
        """Initialize the CachedTokenCredential.

        Args:
            client_id: Azure AD application (client) ID
            tenant_id: Azure AD tenant ID
            token_cache: Optional token cache for access token tracking
            cache_dir: Directory for MSAL token cache (defaults to token_cache dir)
            auth_record_file: File path for persisted authentication record
        """
        self._client_id = client_id
        self._tenant_id = tenant_id
        self._token_cache = token_cache
        self._device_code_credential: Optional[DeviceCodeCredential] = None
        self._auth_record_file = auth_record_file
        self._auth_record: Optional[AuthenticationRecord] = None
        self._prompt_callback = prompt_callback

        # Determine cache directory for MSAL token cache
        if cache_dir:
            self._cache_dir = cache_dir
        elif token_cache:
            self._cache_dir = token_cache.token_file.parent
        else:
            self._cache_dir = Path.home() / ".outmylook"

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        if self._auth_record_file is None:
            self._auth_record_file = self._cache_dir / "auth_record.json"
        self._auth_record = self._load_auth_record()

    def _get_device_code_credential(self) -> DeviceCodeCredential:
        """Get or create the DeviceCodeCredential with persistent cache.

        The credential is configured with TokenCachePersistenceOptions to enable:
        - Persistent storage of access and refresh tokens
        - Silent token refresh using refresh tokens
        - Cross-session authentication
        """
        if self._device_code_credential is None:
            # Enable persistent token caching for refresh token support
            cache_options = TokenCachePersistenceOptions(
                name="outmylook_msal_cache",
                allow_unencrypted_storage=True,  # Required for non-GUI environments
            )

            credential_kwargs: dict[str, Any] = {}
            if self._prompt_callback is not None:
                credential_kwargs["prompt_callback"] = self._prompt_callback
            self._device_code_credential = DeviceCodeCredential(
                client_id=self._client_id,
                tenant_id=self._tenant_id,
                cache_persistence_options=cache_options,
                authentication_record=self._auth_record,
                **credential_kwargs,
            )
            logger.debug("Created DeviceCodeCredential with persistent token cache")

        return self._device_code_credential

    def get_token(
        self,
        *scopes: str,
        claims: Optional[str] = None,
        tenant_id: Optional[str] = None,
        enable_cae: bool = False,
        persist: bool = True,
        **kwargs: Any,
    ) -> AccessToken:
        """Get an access token for the specified scopes.

        The Azure SDK handles token caching and refresh automatically:
        1. If a valid cached access token exists, returns it
        2. If access token expired but refresh token valid, silently refreshes
        3. Only triggers device code flow if no valid tokens exist

        Args:
            *scopes: The scopes for which the token is requested
            claims: Additional claims required in the token
            tenant_id: Optional tenant to use instead of the configured one
            enable_cae: Enable Continuous Access Evaluation
            **kwargs: Additional keyword arguments

        Returns:
            An AccessToken with the token string and expiration time
        """
        # offline_access is reserved. Passing it through makes the MSAL cache key
        # miss a refresh token that was stored without that scope.
        requested_scopes = tuple(scope for scope in scopes if scope != "offline_access") or scopes
        credential = self._get_device_code_credential()

        logger.debug("Requesting token from Azure SDK (will use cache/refresh if available)")
        token = credential.get_token(
            *requested_scopes,
            claims=claims,
            tenant_id=tenant_id,
            enable_cae=enable_cae,
            **kwargs,
        )

        self._persist_auth_record(credential)

        if persist and self._token_cache:
            try:
                self._save_to_cache(token, list(requested_scopes))
            except Exception as e:
                logger.warning(f"Failed to update token cache: {e}")

        return token

    def _save_to_cache(self, token: AccessToken, scopes: list[str]) -> None:
        """Save token to our cache for quick access checks."""
        # If no TokenCache was provided, nothing to do.
        if self._token_cache is None:
            logger.debug("No token cache configured; skipping save.")
            return

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(self._token_cache.save_token(token.token, token.expires_on, scopes))
                logger.debug("Token cached successfully")
                return

            loop.create_task(self._token_cache.save_token(token.token, token.expires_on, scopes))
            logger.debug("Scheduled token cache update")
        except Exception as exc:
            # Don't fail authentication flow if caching fails; just log it.
            logger.debug("Failed to save token to cache: %s", exc)

    def _load_auth_record(self) -> Optional[AuthenticationRecord]:
        if self._auth_record_file is None or not self._auth_record_file.exists():
            return None
        try:
            data = self._auth_record_file.read_text(encoding="utf-8")
            return AuthenticationRecord.deserialize(data)
        except Exception as exc:
            logger.debug("Failed to load authentication record: %s", exc)
            return None

    def _persist_auth_record(self, credential: DeviceCodeCredential) -> None:
        if self._auth_record_file is None:
            return
        auth_record = getattr(credential, "authentication_record", None)
        if auth_record is None:
            auth_record = getattr(credential, "_auth_record", None)
        if not isinstance(auth_record, AuthenticationRecord):
            return
        if self._auth_record and auth_record.serialize() == self._auth_record.serialize():
            return
        try:
            self._auth_record_file.parent.mkdir(parents=True, exist_ok=True)
            self._auth_record_file.write_text(auth_record.serialize(), encoding="utf-8")
            self._auth_record = auth_record
        except Exception as exc:
            logger.debug("Failed to persist authentication record: %s", exc)

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
            "https://graph.microsoft.com/Mail.ReadWrite",
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

    def _create_credential(self, prompt_callback: Optional[Callable[..., None]] = None) -> CachedTokenCredential:
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
            prompt_callback=prompt_callback,
        )

    async def authenticate(self, *, interactive: bool = True) -> GraphServiceClient:
        """Perform device code authentication flow.

        Interactive login waits for the user to enter a device code. Headless
        callers pass ``interactive=False`` so an expired refresh token fails
        immediately instead of blocking a timer.

        Returns:
            Authenticated GraphServiceClient instance

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            if interactive:
                self._credential = self._create_credential()
            else:
                self._credential = self._create_credential(prompt_callback=_refuse_device_code)
            self._client = GraphServiceClient(credentials=self._credential, scopes=self.scopes)

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

    async def recover_cached_session(self) -> bool:
        """Refresh tokens.json from the MSAL cache without user interaction.

        Payroll checks ``status`` hours after the access token expires. A valid
        refresh token is still a signed-in session, so status must renew the
        short-lived access token before reporting the user logged out.
        """
        if not self.client_id:
            return False
        try:
            credential = self._create_credential(prompt_callback=_refuse_device_code)
            scopes = [scope for scope in self.scopes if scope != "offline_access"] or list(self.scopes)
            # persist=False keeps this path to one awaited write. get_token()
            # otherwise schedules a second save on the running event loop.
            token = credential.get_token(*scopes, persist=False)
            if self.token_cache is None:
                return True
            await self.token_cache.save_token(token.token, token.expires_on, scopes)
            return self.token_cache.has_valid_token()
        except Exception as exc:
            logger.info("Silent authentication recovery failed: %s", exc)
            return False

    def is_authenticated(self) -> bool:
        """Check if valid cached token exists.

        Returns:
            True if valid cached token exists, False otherwise
        """
        if not self.token_cache:
            return False
        return self.token_cache.has_valid_token()

    def _auth_record_path(self) -> Path:
        if self.token_cache:
            return Path(self.token_cache.token_file).expanduser().parent / "auth_record.json"
        return Path.home() / ".outmylook" / "auth_record.json"

    async def get_client(self) -> GraphServiceClient:
        """Get authenticated Graph client.

        If not already authenticated, this will initiate the authentication flow.

        Returns:
            Authenticated GraphServiceClient instance

        Raises:
            AuthenticationError: If authentication fails
        """
        if self._client is None:
            return await self.authenticate(interactive=False)
        return self._client

    async def refresh_token(self) -> None:
        """Refresh the access token using the cached refresh token.

        The Azure SDK's DeviceCodeCredential with TokenCachePersistenceOptions
        handles token refresh automatically. This method forces a token refresh
        by requesting a new token - the SDK will use the cached refresh token
        to obtain a new access token silently (without user interaction).

        Only triggers device code flow if the refresh token has expired or
        been revoked.

        Raises:
            AuthenticationError: If token refresh fails
        """
        try:
            logger.info("Refreshing authentication token")

            # Clear our access token cache to ensure we get a fresh token
            if self.token_cache:
                await self.token_cache.clear()

            # Create credential if needed (preserves MSAL cache with refresh token)
            if not self._credential:
                self._credential = self._create_credential()

            # Request new token - Azure SDK will:
            # 1. Check MSAL cache for refresh token
            # 2. Use refresh token to get new access token silently
            # 3. Only trigger device code flow if refresh token is invalid
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
        auth_record_file = self._auth_record_path()
        if auth_record_file.exists():
            try:
                auth_record_file.unlink()
            except Exception as exc:
                logger.debug("Failed to remove auth record: %s", exc)

        self._credential = None
        self._client = None
        logger.info("Logout completed")
