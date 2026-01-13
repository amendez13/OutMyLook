"""Comprehensive tests for authentication module."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.auth import AuthenticationError, CachedTokenCredential, GraphAuthenticator, TokenCache
from src.config.settings import AzureSettings


class TestTokenCache:
    """Tests for TokenCache class."""

    @pytest.fixture
    def token_file(self, tmp_path: Path) -> Path:
        """Create temporary token file path."""
        return tmp_path / "tokens.json"

    @pytest.fixture
    def token_cache(self, token_file: Path) -> TokenCache:
        """Create TokenCache instance with temporary file."""
        return TokenCache(token_file)

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        """Test that TokenCache creates parent directory."""
        token_file = tmp_path / "subdir" / "tokens.json"
        cache = TokenCache(token_file)
        assert cache.token_file.parent.exists()

    @pytest.mark.asyncio
    async def test_save_token(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test saving token to cache."""
        access_token = "test_token_123"
        expires_on = int(datetime.now(timezone.utc).timestamp()) + 3600
        scopes = ["Mail.Read", "User.Read"]

        await token_cache.save_token(access_token, expires_on, scopes)

        assert token_file.exists()

        # Verify file contents
        with open(token_file, "r") as f:
            data = json.load(f)

        assert data["access_token"] == access_token
        assert data["expires_on"] == expires_on
        assert data["scopes"] == scopes
        assert "cached_at" in data

        # Verify file permissions (owner read/write only)
        assert oct(token_file.stat().st_mode)[-3:] == "600"

    @pytest.mark.asyncio
    async def test_load_token(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test loading token from cache."""
        # Save a token first
        test_data = {
            "access_token": "test_token",
            "expires_on": int(datetime.now(timezone.utc).timestamp()) + 3600,
            "scopes": ["Mail.Read"],
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(token_file, "w") as f:
            json.dump(test_data, f)

        loaded = await token_cache.load_token()
        assert loaded == test_data

    @pytest.mark.asyncio
    async def test_load_token_missing_file(self, token_cache: TokenCache) -> None:
        """Test loading token when file doesn't exist."""
        result = await token_cache.load_token()
        assert result is None

    @pytest.mark.asyncio
    async def test_load_token_invalid_json(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test loading token with invalid JSON."""
        with open(token_file, "w") as f:
            f.write("invalid json {")

        result = await token_cache.load_token()
        assert result is None

    def test_has_valid_token_missing_file(self, token_cache: TokenCache) -> None:
        """Test has_valid_token when file doesn't exist."""
        assert not token_cache.has_valid_token()

    def test_has_valid_token_expired(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test has_valid_token with expired token."""
        expired_data = {
            "access_token": "token",
            "expires_on": int(datetime.now(timezone.utc).timestamp()) - 100,  # Expired
            "scopes": ["Mail.Read"],
        }

        with open(token_file, "w") as f:
            json.dump(expired_data, f)

        assert not token_cache.has_valid_token()

    def test_has_valid_token_expiring_soon(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test has_valid_token with token expiring within buffer."""
        # Token expires in 2 minutes (less than 5 minute buffer)
        expires_soon_data = {
            "access_token": "token",
            "expires_on": int(datetime.now(timezone.utc).timestamp()) + 120,
            "scopes": ["Mail.Read"],
        }

        with open(token_file, "w") as f:
            json.dump(expires_soon_data, f)

        assert not token_cache.has_valid_token()

    def test_has_valid_token_valid(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test has_valid_token with valid token."""
        valid_data = {
            "access_token": "token",
            "expires_on": int(datetime.now(timezone.utc).timestamp()) + 3600,  # 1 hour
            "scopes": ["Mail.Read"],
        }

        with open(token_file, "w") as f:
            json.dump(valid_data, f)

        assert token_cache.has_valid_token()

    def test_has_valid_token_missing_fields(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test has_valid_token with missing required fields."""
        incomplete_data = {"access_token": "token"}  # Missing expires_on

        with open(token_file, "w") as f:
            json.dump(incomplete_data, f)

        assert not token_cache.has_valid_token()

    @pytest.mark.asyncio
    async def test_clear(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test clearing token cache."""
        # Create a token file
        with open(token_file, "w") as f:
            json.dump({"access_token": "token", "expires_on": 123456}, f)

        assert token_file.exists()

        await token_cache.clear()

        assert not token_file.exists()

    @pytest.mark.asyncio
    async def test_clear_missing_file(self, token_cache: TokenCache) -> None:
        """Test clearing cache when file doesn't exist."""
        # Should not raise error
        await token_cache.clear()

    @pytest.mark.asyncio
    async def test_get_access_token(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test getting access token from cache."""
        valid_data = {
            "access_token": "test_token_123",
            "expires_on": int(datetime.now(timezone.utc).timestamp()) + 3600,
            "scopes": ["Mail.Read"],
        }

        with open(token_file, "w") as f:
            json.dump(valid_data, f)

        token = await token_cache.get_access_token()
        assert token == "test_token_123"

    @pytest.mark.asyncio
    async def test_get_access_token_invalid(self, token_cache: TokenCache) -> None:
        """Test getting access token with invalid cache."""
        token = await token_cache.get_access_token()
        assert token is None

    @pytest.mark.asyncio
    async def test_get_token_info(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test getting full token information."""
        expires_on = int(datetime.now(timezone.utc).timestamp()) + 3600
        cached_at = datetime.now(timezone.utc).isoformat()

        valid_data = {
            "access_token": "token",
            "expires_on": expires_on,
            "scopes": ["Mail.Read", "User.Read"],
            "cached_at": cached_at,
        }

        with open(token_file, "w") as f:
            json.dump(valid_data, f)

        info = await token_cache.get_token_info()

        assert info is not None
        assert info["expires_on"] == expires_on
        assert "expires_at" in info
        assert info["scopes"] == ["Mail.Read", "User.Read"]
        assert info["cached_at"] == cached_at
        assert info["seconds_until_expiry"] > 0

    @pytest.mark.asyncio
    async def test_get_token_info_invalid(self, token_cache: TokenCache) -> None:
        """Test getting token info with invalid cache."""
        info = await token_cache.get_token_info()
        assert info is None

    def test_is_token_expiring_soon_default_threshold(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test checking if token is expiring soon with default threshold."""
        # Token expires in 2 minutes (less than 5 minute default)
        expires_soon_data = {
            "access_token": "token",
            "expires_on": int(datetime.now(timezone.utc).timestamp()) + 120,
        }

        with open(token_file, "w") as f:
            json.dump(expires_soon_data, f)

        assert token_cache.is_token_expiring_soon()

    def test_is_token_expiring_soon_custom_threshold(self, token_cache: TokenCache, token_file: Path) -> None:
        """Test checking if token is expiring soon with custom threshold."""
        # Token expires in 10 minutes
        expires_data = {
            "access_token": "token",
            "expires_on": int(datetime.now(timezone.utc).timestamp()) + 600,
        }

        with open(token_file, "w") as f:
            json.dump(expires_data, f)

        # With 15 minute threshold, should be expiring soon
        assert token_cache.is_token_expiring_soon(threshold_seconds=900)

        # With 5 minute threshold, should not be expiring soon
        assert not token_cache.is_token_expiring_soon(threshold_seconds=300)


class TestGraphAuthenticator:
    """Tests for GraphAuthenticator class."""

    @pytest.fixture
    def azure_settings(self) -> AzureSettings:
        """Create AzureSettings instance."""
        return AzureSettings(
            client_id="test-client-id",
            tenant="common",
            scopes=["Mail.Read", "User.Read", "offline_access"],
        )

    @pytest.fixture
    def mock_token_cache(self, tmp_path: Path) -> Mock:
        """Create mock TokenCache."""
        cache = Mock(spec=TokenCache)
        cache.has_valid_token.return_value = False
        cache.save_token = AsyncMock()
        cache.clear = AsyncMock()
        # Add token_file attribute for CachedTokenCredential cache_dir detection
        cache.token_file = tmp_path / "tokens.json"
        return cache

    @pytest.fixture
    def authenticator(self, azure_settings: AzureSettings, mock_token_cache: Mock) -> GraphAuthenticator:
        """Create GraphAuthenticator instance."""
        return GraphAuthenticator(
            client_id=azure_settings.client_id,
            tenant=azure_settings.tenant,
            scopes=azure_settings.scopes,
            token_cache=mock_token_cache,
        )

    def test_init(self, authenticator: GraphAuthenticator) -> None:
        """Test GraphAuthenticator initialization."""
        assert authenticator.client_id == "test-client-id"
        assert authenticator.tenant == "common"
        assert "Mail.Read" in authenticator.scopes
        assert authenticator.token_cache is not None

    def test_init_default_scopes(self) -> None:
        """Test GraphAuthenticator with default scopes."""
        auth = GraphAuthenticator(client_id="test-client-id")
        assert "https://graph.microsoft.com/Mail.Read" in auth.scopes
        assert "https://graph.microsoft.com/User.Read" in auth.scopes
        assert "offline_access" in auth.scopes

    def test_from_settings(self, azure_settings: AzureSettings, mock_token_cache: Mock) -> None:
        """Test creating authenticator from settings."""
        auth = GraphAuthenticator.from_settings(azure_settings, mock_token_cache)
        assert auth.client_id == azure_settings.client_id
        assert auth.tenant == azure_settings.tenant
        assert auth.scopes == azure_settings.scopes

    def test_create_credential(self, authenticator: GraphAuthenticator) -> None:
        """Test creating CachedTokenCredential."""
        from src.auth.authenticator import CachedTokenCredential

        credential = authenticator._create_credential()

        assert isinstance(credential, CachedTokenCredential)
        assert credential._client_id == "test-client-id"
        assert credential._tenant_id == "common"
        assert credential._token_cache == authenticator.token_cache

    def test_create_credential_no_client_id(self) -> None:
        """Test creating credential without client_id raises error."""
        auth = GraphAuthenticator(client_id="")

        with pytest.raises(AuthenticationError, match="client_id not configured"):
            auth._create_credential()

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.GraphServiceClient")
    async def test_authenticate_success(
        self,
        mock_graph_client: Mock,
        authenticator: GraphAuthenticator,
    ) -> None:
        """Test successful authentication."""
        # Setup mocks
        mock_user = Mock()
        mock_user.user_principal_name = "test@example.com"
        mock_user.display_name = "Test User"

        mock_client_instance = Mock()
        mock_client_instance.me.get = AsyncMock(return_value=mock_user)
        mock_graph_client.return_value = mock_client_instance

        # Mock the credential's get_token to avoid actual device code flow
        with patch.object(authenticator, "_create_credential") as mock_create:
            mock_credential = Mock()
            mock_credential.get_token = Mock(return_value=Mock(token="test_token", expires_on=123456))
            mock_create.return_value = mock_credential

            # Authenticate
            client = await authenticator.authenticate()

            assert client == mock_client_instance
            # Credential is created and used
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.GraphServiceClient")
    async def test_authenticate_cached_token(
        self,
        mock_graph_client: Mock,
        authenticator: GraphAuthenticator,
    ) -> None:
        """Test authentication with valid cached token uses cache instead of device flow."""
        # Setup token cache to return valid token
        authenticator.token_cache.has_valid_token.return_value = True
        authenticator.token_cache._read_token_file = Mock(return_value={"access_token": "cached_token", "expires_on": 123456})

        mock_user = Mock()
        mock_user.user_principal_name = "test@example.com"

        mock_client_instance = Mock()
        mock_client_instance.me.get = AsyncMock(return_value=mock_user)
        mock_graph_client.return_value = mock_client_instance

        # Authenticate - CachedTokenCredential will use the cached token
        client = await authenticator.authenticate()

        # Should return the client
        assert client == mock_client_instance
        # Credential should be created (CachedTokenCredential)
        assert authenticator._credential is not None

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.GraphServiceClient")
    async def test_authenticate_failure(
        self,
        mock_graph_client: Mock,
        authenticator: GraphAuthenticator,
    ) -> None:
        """Test authentication failure."""
        mock_client_instance = Mock()
        mock_client_instance.me.get = AsyncMock(side_effect=Exception("API Error"))
        mock_graph_client.return_value = mock_client_instance

        # Mock the credential to avoid device code flow
        with patch.object(authenticator, "_create_credential") as mock_create:
            mock_credential = Mock()
            mock_create.return_value = mock_credential

            with pytest.raises(AuthenticationError, match="Authentication failed"):
                await authenticator.authenticate()

    def test_is_authenticated_no_cache(self) -> None:
        """Test is_authenticated without token cache."""
        auth = GraphAuthenticator(client_id="test-id", token_cache=None)
        assert not auth.is_authenticated()

    def test_is_authenticated_with_valid_token(self, authenticator: GraphAuthenticator) -> None:
        """Test is_authenticated with valid token."""
        authenticator.token_cache.has_valid_token.return_value = True
        assert authenticator.is_authenticated()

    def test_is_authenticated_with_invalid_token(self, authenticator: GraphAuthenticator) -> None:
        """Test is_authenticated with invalid token."""
        authenticator.token_cache.has_valid_token.return_value = False
        assert not authenticator.is_authenticated()

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.GraphServiceClient")
    async def test_get_client_not_authenticated(
        self,
        mock_graph_client: Mock,
        authenticator: GraphAuthenticator,
    ) -> None:
        """Test get_client when not authenticated."""
        mock_user = Mock()
        mock_user.user_principal_name = "test@example.com"

        mock_client_instance = Mock()
        mock_client_instance.me.get = AsyncMock(return_value=mock_user)
        mock_graph_client.return_value = mock_client_instance

        # Mock the credential to avoid device code flow
        with patch.object(authenticator, "_create_credential") as mock_create:
            mock_credential = Mock()
            mock_credential.get_token = Mock(return_value=Mock(token="token", expires_on=123456))
            mock_create.return_value = mock_credential

            client = await authenticator.get_client()

            assert client == mock_client_instance

    @pytest.mark.asyncio
    async def test_get_client_already_authenticated(self, authenticator: GraphAuthenticator) -> None:
        """Test get_client when already authenticated."""
        mock_client = Mock()
        authenticator._client = mock_client

        client = await authenticator.get_client()

        assert client == mock_client

    @pytest.mark.asyncio
    async def test_refresh_token_with_existing_credential(self, authenticator: GraphAuthenticator) -> None:
        """Test token refresh uses existing credential (preserves MSAL cache)."""
        # Set up existing credential
        mock_credential = Mock()
        mock_credential.get_token = Mock(return_value=Mock(token="refreshed_token", expires_on=789012))
        authenticator._credential = mock_credential

        await authenticator.refresh_token()

        # Cache should be cleared
        authenticator.token_cache.clear.assert_called_once()
        # Existing credential should be reused (not recreated)
        mock_credential.get_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_token_creates_credential_if_none(self, authenticator: GraphAuthenticator) -> None:
        """Test token refresh creates credential if none exists."""
        authenticator._credential = None

        with patch.object(authenticator, "_create_credential") as mock_create:
            mock_credential = Mock()
            mock_credential.get_token = Mock(return_value=Mock(token="new_token", expires_on=789012))
            mock_create.return_value = mock_credential

            await authenticator.refresh_token()

            # Cache should be cleared first
            authenticator.token_cache.clear.assert_called_once()
            # New credential should be created since none existed
            mock_create.assert_called_once()
            # get_token should be called to get fresh token
            mock_credential.get_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_token_failure(self, authenticator: GraphAuthenticator) -> None:
        """Test token refresh failure."""
        mock_credential = Mock()
        mock_credential.get_token = Mock(side_effect=Exception("Refresh failed"))
        authenticator._credential = mock_credential

        with pytest.raises(AuthenticationError, match="Token refresh failed"):
            await authenticator.refresh_token()

    @pytest.mark.asyncio
    async def test_logout(self, authenticator: GraphAuthenticator) -> None:
        """Test logout."""
        authenticator._credential = Mock()
        authenticator._client = Mock()
        auth_record_file = authenticator._auth_record_path()
        auth_record_file.parent.mkdir(parents=True, exist_ok=True)
        auth_record_file.write_text("record", encoding="utf-8")

        await authenticator.logout()

        authenticator.token_cache.clear.assert_called_once()
        assert not auth_record_file.exists()
        assert authenticator._credential is None
        assert authenticator._client is None

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.GraphServiceClient")
    async def test_authenticate_no_user_principal_name(
        self,
        mock_graph_client: Mock,
        authenticator: GraphAuthenticator,
    ) -> None:
        """Test authentication failure when user has no principal name."""
        mock_user = Mock()
        mock_user.user_principal_name = None  # No principal name

        mock_client_instance = Mock()
        mock_client_instance.me.get = AsyncMock(return_value=mock_user)
        mock_graph_client.return_value = mock_client_instance

        with patch.object(authenticator, "_create_credential") as mock_create:
            mock_credential = Mock()
            mock_create.return_value = mock_credential

            with pytest.raises(AuthenticationError, match="Failed to retrieve user information"):
                await authenticator.authenticate()

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.GraphServiceClient")
    async def test_authenticate_reraises_authentication_error(
        self,
        mock_graph_client: Mock,
        authenticator: GraphAuthenticator,
    ) -> None:
        """Test that AuthenticationError is re-raised without wrapping."""
        mock_client_instance = Mock()
        mock_client_instance.me.get = AsyncMock(side_effect=AuthenticationError("Original error"))
        mock_graph_client.return_value = mock_client_instance

        with patch.object(authenticator, "_create_credential") as mock_create:
            mock_credential = Mock()
            mock_create.return_value = mock_credential

            with pytest.raises(AuthenticationError, match="Original error"):
                await authenticator.authenticate()


class TestCachedTokenCredential:
    """Tests for CachedTokenCredential class."""

    @pytest.fixture
    def mock_token_cache(self, tmp_path: Path) -> Mock:
        """Create mock TokenCache."""
        cache = Mock(spec=TokenCache)
        cache.has_valid_token.return_value = False
        cache.save_token = AsyncMock()
        # Add token_file attribute for cache_dir detection
        cache.token_file = tmp_path / "tokens.json"
        return cache

    @pytest.fixture
    def credential(self, mock_token_cache: Mock) -> "CachedTokenCredential":
        """Create CachedTokenCredential instance."""
        from src.auth.authenticator import CachedTokenCredential

        return CachedTokenCredential(
            client_id="test-client-id",
            tenant_id="test-tenant",
            token_cache=mock_token_cache,
        )

    def test_init(self, credential: "CachedTokenCredential") -> None:
        """Test CachedTokenCredential initialization."""
        assert credential._client_id == "test-client-id"
        assert credential._tenant_id == "test-tenant"
        assert credential._token_cache is not None
        assert credential._device_code_credential is None

    def test_init_with_explicit_cache_dir(self, tmp_path: Path) -> None:
        """Test CachedTokenCredential with explicit cache_dir."""
        from src.auth.authenticator import CachedTokenCredential

        cache_dir = tmp_path / "custom_cache"
        credential = CachedTokenCredential(
            client_id="test-client-id",
            tenant_id="test-tenant",
            cache_dir=cache_dir,
        )

        assert credential._cache_dir == cache_dir
        assert cache_dir.exists()  # Should be created

    @patch("src.auth.authenticator.DeviceCodeCredential")
    def test_get_device_code_credential_creates_once(
        self, mock_device_code: Mock, credential: "CachedTokenCredential"
    ) -> None:
        """Test that DeviceCodeCredential is created only once."""
        mock_device_code.return_value = Mock()

        # First call creates it
        cred1 = credential._get_device_code_credential()
        assert mock_device_code.call_count == 1

        # Second call returns cached instance
        cred2 = credential._get_device_code_credential()
        assert mock_device_code.call_count == 1
        assert cred1 is cred2

    def test_get_device_code_credential_uses_auth_record(self, tmp_path: Path, mock_token_cache: Mock) -> None:
        """_get_device_code_credential should pass authentication_record when available."""
        from azure.identity import AuthenticationRecord

        from src.auth.authenticator import CachedTokenCredential

        auth_record = AuthenticationRecord(
            tenant_id="tenant",
            client_id="client",
            authority="login.microsoftonline.com",
            home_account_id="home-id",
            username="user@example.com",
        )
        auth_record_file = tmp_path / "auth_record.json"
        auth_record_file.write_text(auth_record.serialize(), encoding="utf-8")

        credential = CachedTokenCredential(
            client_id="test-client-id",
            tenant_id="test-tenant",
            token_cache=mock_token_cache,
            auth_record_file=auth_record_file,
        )

        with patch("src.auth.authenticator.DeviceCodeCredential") as mock_device_code:
            mock_device_code.return_value = Mock()
            credential._get_device_code_credential()

        called_kwargs = mock_device_code.call_args.kwargs
        assert called_kwargs["authentication_record"].username == "user@example.com"

    def test_get_token_delegates_to_azure_sdk(self, credential: "CachedTokenCredential") -> None:
        """Test get_token delegates to Azure SDK's DeviceCodeCredential."""
        with patch.object(credential, "_get_device_code_credential") as mock_get_cred:
            mock_device_cred = Mock()
            mock_device_cred.get_token.return_value = Mock(token="sdk_token", expires_on=123456)
            mock_get_cred.return_value = mock_device_cred

            token = credential.get_token("scope1", "scope2")

            assert token.token == "sdk_token"
            assert token.expires_on == 123456
            mock_get_cred.assert_called_once()
            mock_device_cred.get_token.assert_called_once()

    def test_get_token_updates_local_cache(self, credential: "CachedTokenCredential") -> None:
        """Test get_token updates our local cache after getting token from SDK."""
        with patch.object(credential, "_get_device_code_credential") as mock_get_cred:
            mock_device_cred = Mock()
            mock_device_cred.get_token.return_value = Mock(token="new_token", expires_on=123456)
            mock_get_cred.return_value = mock_device_cred

            with patch.object(credential, "_save_to_cache") as mock_save:
                token = credential.get_token("scope1")

                assert token.token == "new_token"
                mock_save.assert_called_once()

    def test_get_token_persists_auth_record(self, tmp_path: Path, mock_token_cache: Mock) -> None:
        """get_token should persist AuthenticationRecord when available."""
        from azure.identity import AuthenticationRecord

        from src.auth.authenticator import CachedTokenCredential

        auth_record_file = tmp_path / "auth_record.json"
        credential = CachedTokenCredential(
            client_id="test-client-id",
            tenant_id="test-tenant",
            token_cache=mock_token_cache,
            auth_record_file=auth_record_file,
        )

        auth_record = AuthenticationRecord(
            tenant_id="tenant",
            client_id="client",
            authority="login.microsoftonline.com",
            home_account_id="home-id",
            username="user@example.com",
        )

        mock_device_cred = Mock()
        mock_device_cred.get_token.return_value = Mock(token="new_token", expires_on=123456)
        mock_device_cred.authentication_record = auth_record

        with patch.object(credential, "_get_device_code_credential", return_value=mock_device_cred):
            credential.get_token("scope1")

        assert auth_record_file.exists()
        stored = AuthenticationRecord.deserialize(auth_record_file.read_text(encoding="utf-8"))
        assert stored.username == "user@example.com"

    @patch("src.auth.authenticator.asyncio")
    def test_save_to_cache_with_event_loop(self, mock_asyncio: Mock, credential: "CachedTokenCredential") -> None:
        """Test _save_to_cache uses event loop when available."""
        mock_loop = Mock()
        mock_asyncio.get_running_loop.return_value = mock_loop

        token = Mock(token="new_token", expires_on=123456)
        credential._save_to_cache(token, ["scope1", "scope2"])

        mock_loop.create_task.assert_called_once()

    def test_save_to_cache_without_token_cache(self) -> None:
        """_save_to_cache should no-op when no TokenCache is configured."""
        from src.auth.authenticator import CachedTokenCredential

        credential = CachedTokenCredential(
            client_id="test-client-id",
            tenant_id="test-tenant",
            token_cache=None,
        )
        token = Mock(token="new_token", expires_on=123456)
        credential._save_to_cache(token, ["scope1"])

    @patch("src.auth.authenticator.asyncio")
    def test_save_to_cache_handles_exception(self, mock_asyncio: Mock, credential: "CachedTokenCredential") -> None:
        """_save_to_cache should handle scheduling errors gracefully."""
        mock_loop = Mock()
        mock_loop.create_task.side_effect = RuntimeError("boom")
        mock_asyncio.get_running_loop.return_value = mock_loop

        token = Mock(token="new_token", expires_on=123456)
        credential._save_to_cache(token, ["scope1"])

    @patch("src.auth.authenticator.asyncio")
    def test_save_to_cache_without_event_loop(self, mock_asyncio: Mock, credential: "CachedTokenCredential") -> None:
        """Test _save_to_cache uses asyncio.run when no event loop."""
        mock_asyncio.get_running_loop.side_effect = RuntimeError("No event loop")

        token = Mock(token="new_token", expires_on=123456)
        credential._save_to_cache(token, ["scope1"])

        mock_asyncio.run.assert_called_once()

    def test_load_auth_record_invalid_returns_none(self, tmp_path: Path, mock_token_cache: Mock) -> None:
        """Invalid auth record data should be ignored."""
        from src.auth.authenticator import CachedTokenCredential

        auth_record_file = tmp_path / "auth_record.json"
        auth_record_file.write_text("not-json", encoding="utf-8")

        credential = CachedTokenCredential(
            client_id="test-client-id",
            tenant_id="test-tenant",
            token_cache=mock_token_cache,
            auth_record_file=auth_record_file,
        )

        assert credential._auth_record is None

    def test_persist_auth_record_skips_when_disabled(self, credential: "CachedTokenCredential") -> None:
        """_persist_auth_record should no-op without a record file."""
        mock_device = Mock()
        credential._auth_record_file = None
        credential._persist_auth_record(mock_device)

    def test_persist_auth_record_skips_invalid_record(self, tmp_path: Path, mock_token_cache: Mock) -> None:
        """_persist_auth_record should ignore invalid auth record types."""
        from src.auth.authenticator import CachedTokenCredential

        auth_record_file = tmp_path / "auth_record.json"
        credential = CachedTokenCredential(
            client_id="test-client-id",
            tenant_id="test-tenant",
            token_cache=mock_token_cache,
            auth_record_file=auth_record_file,
        )

        mock_device = Mock()
        mock_device._auth_record = "bad-record"
        credential._persist_auth_record(mock_device)
        assert not auth_record_file.exists()

    def test_persist_auth_record_skips_duplicates(self, tmp_path: Path, mock_token_cache: Mock) -> None:
        """_persist_auth_record should skip writing duplicate records."""
        from azure.identity import AuthenticationRecord

        from src.auth.authenticator import CachedTokenCredential

        auth_record_file = tmp_path / "auth_record.json"
        auth_record = AuthenticationRecord(
            tenant_id="tenant",
            client_id="client",
            authority="login.microsoftonline.com",
            home_account_id="home-id",
            username="user@example.com",
        )

        credential = CachedTokenCredential(
            client_id="test-client-id",
            tenant_id="test-tenant",
            token_cache=mock_token_cache,
            auth_record_file=auth_record_file,
        )
        credential._auth_record = auth_record

        mock_device = Mock()
        mock_device._auth_record = auth_record
        credential._persist_auth_record(mock_device)
        assert not auth_record_file.exists()

    def test_persist_auth_record_handles_write_failure(self, tmp_path: Path, mock_token_cache: Mock) -> None:
        """_persist_auth_record should swallow write failures."""
        from azure.identity import AuthenticationRecord

        from src.auth.authenticator import CachedTokenCredential

        auth_record_file = tmp_path / "auth_record.json"
        credential = CachedTokenCredential(
            client_id="test-client-id",
            tenant_id="test-tenant",
            token_cache=mock_token_cache,
            auth_record_file=auth_record_file,
        )

        auth_record = AuthenticationRecord(
            tenant_id="tenant",
            client_id="client",
            authority="login.microsoftonline.com",
            home_account_id="home-id",
            username="user@example.com",
        )

        mock_device = Mock()
        mock_device._auth_record = auth_record

        with patch.object(Path, "write_text", side_effect=RuntimeError("boom")):
            credential._persist_auth_record(mock_device)

    def test_get_token_handles_cache_save_failure(self, credential: "CachedTokenCredential") -> None:
        """Test get_token handles cache save failures gracefully."""
        with patch.object(credential, "_get_device_code_credential") as mock_get_cred:
            mock_device_cred = Mock()
            mock_device_cred.get_token.return_value = Mock(token="new_token", expires_on=123456)
            mock_get_cred.return_value = mock_device_cred

            with patch.object(credential, "_save_to_cache", side_effect=Exception("Save failed")):
                # Should not raise, just log warning
                token = credential.get_token("scope1")

                assert token.token == "new_token"

    def test_get_token_no_cache(self) -> None:
        """Test get_token works without token cache."""
        from src.auth.authenticator import CachedTokenCredential

        credential = CachedTokenCredential(
            client_id="test-client-id",
            tenant_id="test-tenant",
            token_cache=None,
        )

        with patch.object(credential, "_get_device_code_credential") as mock_get_cred:
            mock_device_cred = Mock()
            mock_device_cred.get_token.return_value = Mock(token="new_token", expires_on=123456)
            mock_get_cred.return_value = mock_device_cred

            token = credential.get_token("scope1")

            assert token.token == "new_token"

    @pytest.mark.asyncio
    async def test_close_with_device_credential(self, credential: "CachedTokenCredential") -> None:
        """Test close calls close on device code credential."""
        mock_device_cred = Mock()
        credential._device_code_credential = mock_device_cred

        await credential.close()

        mock_device_cred.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_device_credential(self, credential: "CachedTokenCredential") -> None:
        """Test close does nothing when no device credential exists."""
        credential._device_code_credential = None

        # Should not raise
        await credential.close()
