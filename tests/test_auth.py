"""Comprehensive tests for authentication module."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.auth import AuthenticationError, GraphAuthenticator, TokenCache, TokenCacheError
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
    async def test_load_token(
        self, token_cache: TokenCache, token_file: Path
    ) -> None:
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
    async def test_load_token_invalid_json(
        self, token_cache: TokenCache, token_file: Path
    ) -> None:
        """Test loading token with invalid JSON."""
        with open(token_file, "w") as f:
            f.write("invalid json {")

        result = await token_cache.load_token()
        assert result is None

    def test_has_valid_token_missing_file(self, token_cache: TokenCache) -> None:
        """Test has_valid_token when file doesn't exist."""
        assert not token_cache.has_valid_token()

    def test_has_valid_token_expired(
        self, token_cache: TokenCache, token_file: Path
    ) -> None:
        """Test has_valid_token with expired token."""
        expired_data = {
            "access_token": "token",
            "expires_on": int(datetime.now(timezone.utc).timestamp()) - 100,  # Expired
            "scopes": ["Mail.Read"],
        }

        with open(token_file, "w") as f:
            json.dump(expired_data, f)

        assert not token_cache.has_valid_token()

    def test_has_valid_token_expiring_soon(
        self, token_cache: TokenCache, token_file: Path
    ) -> None:
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

    def test_has_valid_token_valid(
        self, token_cache: TokenCache, token_file: Path
    ) -> None:
        """Test has_valid_token with valid token."""
        valid_data = {
            "access_token": "token",
            "expires_on": int(datetime.now(timezone.utc).timestamp()) + 3600,  # 1 hour
            "scopes": ["Mail.Read"],
        }

        with open(token_file, "w") as f:
            json.dump(valid_data, f)

        assert token_cache.has_valid_token()

    def test_has_valid_token_missing_fields(
        self, token_cache: TokenCache, token_file: Path
    ) -> None:
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
    async def test_get_access_token(
        self, token_cache: TokenCache, token_file: Path
    ) -> None:
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
    async def test_get_token_info(
        self, token_cache: TokenCache, token_file: Path
    ) -> None:
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

    def test_is_token_expiring_soon_default_threshold(
        self, token_cache: TokenCache, token_file: Path
    ) -> None:
        """Test checking if token is expiring soon with default threshold."""
        # Token expires in 2 minutes (less than 5 minute default)
        expires_soon_data = {
            "access_token": "token",
            "expires_on": int(datetime.now(timezone.utc).timestamp()) + 120,
        }

        with open(token_file, "w") as f:
            json.dump(expires_soon_data, f)

        assert token_cache.is_token_expiring_soon()

    def test_is_token_expiring_soon_custom_threshold(
        self, token_cache: TokenCache, token_file: Path
    ) -> None:
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
    def mock_token_cache(self) -> Mock:
        """Create mock TokenCache."""
        cache = Mock(spec=TokenCache)
        cache.has_valid_token.return_value = False
        cache.save_token = AsyncMock()
        cache.clear = AsyncMock()
        return cache

    @pytest.fixture
    def authenticator(
        self, azure_settings: AzureSettings, mock_token_cache: Mock
    ) -> GraphAuthenticator:
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

    def test_from_settings(
        self, azure_settings: AzureSettings, mock_token_cache: Mock
    ) -> None:
        """Test creating authenticator from settings."""
        auth = GraphAuthenticator.from_settings(azure_settings, mock_token_cache)
        assert auth.client_id == azure_settings.client_id
        assert auth.tenant == azure_settings.tenant
        assert auth.scopes == azure_settings.scopes

    @patch("src.auth.authenticator.DeviceCodeCredential")
    def test_create_credential(
        self, mock_device_code: Mock, authenticator: GraphAuthenticator
    ) -> None:
        """Test creating device code credential."""
        credential = authenticator._create_credential()

        mock_device_code.assert_called_once_with(
            client_id="test-client-id",
            tenant_id="common",
        )

    def test_create_credential_no_client_id(self) -> None:
        """Test creating credential without client_id raises error."""
        auth = GraphAuthenticator(client_id="")

        with pytest.raises(AuthenticationError, match="client_id not configured"):
            auth._create_credential()

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.GraphServiceClient")
    @patch("src.auth.authenticator.DeviceCodeCredential")
    async def test_authenticate_success(
        self,
        mock_device_code: Mock,
        mock_graph_client: Mock,
        authenticator: GraphAuthenticator,
    ) -> None:
        """Test successful authentication."""
        # Setup mocks
        mock_credential = Mock()
        mock_credential.get_token = AsyncMock(
            return_value=Mock(token="test_token", expires_on=123456)
        )
        mock_device_code.return_value = mock_credential

        mock_user = Mock()
        mock_user.user_principal_name = "test@example.com"
        mock_user.display_name = "Test User"

        mock_client_instance = Mock()
        mock_client_instance.me.get = AsyncMock(return_value=mock_user)
        mock_graph_client.return_value = mock_client_instance

        # Authenticate
        client = await authenticator.authenticate()

        assert client == mock_client_instance
        authenticator.token_cache.save_token.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.GraphServiceClient")
    @patch("src.auth.authenticator.DeviceCodeCredential")
    async def test_authenticate_cached_token(
        self,
        mock_device_code: Mock,
        mock_graph_client: Mock,
        authenticator: GraphAuthenticator,
    ) -> None:
        """Test authentication with valid cached token."""
        # Setup token cache to return valid token
        authenticator.token_cache.has_valid_token.return_value = True

        mock_credential = Mock()
        mock_credential.get_token = AsyncMock(
            return_value=Mock(token="cached_token", expires_on=123456)
        )
        mock_device_code.return_value = mock_credential

        mock_user = Mock()
        mock_user.user_principal_name = "test@example.com"

        mock_client_instance = Mock()
        mock_client_instance.me.get = AsyncMock(return_value=mock_user)
        mock_graph_client.return_value = mock_client_instance

        # Authenticate
        await authenticator.authenticate()

        # Should still create credential and client
        assert mock_device_code.called

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.GraphServiceClient")
    @patch("src.auth.authenticator.DeviceCodeCredential")
    async def test_authenticate_failure(
        self,
        mock_device_code: Mock,
        mock_graph_client: Mock,
        authenticator: GraphAuthenticator,
    ) -> None:
        """Test authentication failure."""
        mock_device_code.return_value = Mock()

        mock_client_instance = Mock()
        mock_client_instance.me.get = AsyncMock(side_effect=Exception("API Error"))
        mock_graph_client.return_value = mock_client_instance

        with pytest.raises(AuthenticationError, match="Authentication failed"):
            await authenticator.authenticate()

    def test_is_authenticated_no_cache(self) -> None:
        """Test is_authenticated without token cache."""
        auth = GraphAuthenticator(client_id="test-id", token_cache=None)
        assert not auth.is_authenticated()

    def test_is_authenticated_with_valid_token(
        self, authenticator: GraphAuthenticator
    ) -> None:
        """Test is_authenticated with valid token."""
        authenticator.token_cache.has_valid_token.return_value = True
        assert authenticator.is_authenticated()

    def test_is_authenticated_with_invalid_token(
        self, authenticator: GraphAuthenticator
    ) -> None:
        """Test is_authenticated with invalid token."""
        authenticator.token_cache.has_valid_token.return_value = False
        assert not authenticator.is_authenticated()

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.GraphServiceClient")
    @patch("src.auth.authenticator.DeviceCodeCredential")
    async def test_get_client_not_authenticated(
        self,
        mock_device_code: Mock,
        mock_graph_client: Mock,
        authenticator: GraphAuthenticator,
    ) -> None:
        """Test get_client when not authenticated."""
        mock_credential = Mock()
        mock_credential.get_token = AsyncMock(
            return_value=Mock(token="token", expires_on=123456)
        )
        mock_device_code.return_value = mock_credential

        mock_user = Mock()
        mock_user.user_principal_name = "test@example.com"

        mock_client_instance = Mock()
        mock_client_instance.me.get = AsyncMock(return_value=mock_user)
        mock_graph_client.return_value = mock_client_instance

        client = await authenticator.get_client()

        assert client == mock_client_instance

    @pytest.mark.asyncio
    async def test_get_client_already_authenticated(
        self, authenticator: GraphAuthenticator
    ) -> None:
        """Test get_client when already authenticated."""
        mock_client = Mock()
        authenticator._client = mock_client

        client = await authenticator.get_client()

        assert client == mock_client

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.DeviceCodeCredential")
    async def test_refresh_token(
        self, mock_device_code: Mock, authenticator: GraphAuthenticator
    ) -> None:
        """Test token refresh."""
        mock_credential = Mock()
        mock_credential.get_token = AsyncMock(
            return_value=Mock(token="new_token", expires_on=789012)
        )
        mock_device_code.return_value = mock_credential

        await authenticator.refresh_token()

        authenticator.token_cache.save_token.assert_called_once_with(
            "new_token", 789012, authenticator.scopes
        )

    @pytest.mark.asyncio
    @patch("src.auth.authenticator.DeviceCodeCredential")
    async def test_refresh_token_failure(
        self, mock_device_code: Mock, authenticator: GraphAuthenticator
    ) -> None:
        """Test token refresh failure."""
        mock_credential = Mock()
        mock_credential.get_token = AsyncMock(side_effect=Exception("Refresh failed"))
        mock_device_code.return_value = mock_credential

        with pytest.raises(AuthenticationError, match="Token refresh failed"):
            await authenticator.refresh_token()

    @pytest.mark.asyncio
    async def test_logout(self, authenticator: GraphAuthenticator) -> None:
        """Test logout."""
        authenticator._credential = Mock()
        authenticator._client = Mock()

        await authenticator.logout()

        authenticator.token_cache.clear.assert_called_once()
        assert authenticator._credential is None
        assert authenticator._client is None
