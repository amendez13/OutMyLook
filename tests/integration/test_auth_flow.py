"""Integration tests for authentication flow with mocked Graph API."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.auth import GraphAuthenticator, TokenCache


@pytest.mark.asyncio
async def test_auth_flow_authenticates_with_mocked_graph(tmp_path, graph_user) -> None:
    """authenticate should return a Graph client when Graph API responds."""
    token_cache = TokenCache(tmp_path / "tokens.json")
    authenticator = GraphAuthenticator(client_id="client-id", scopes=["scope"], token_cache=token_cache)

    fake_client = Mock()
    fake_client.me.get = AsyncMock(return_value=graph_user)

    with (
        patch("src.auth.authenticator.GraphServiceClient", return_value=fake_client) as graph_client_cls,
        patch.object(authenticator, "_create_credential", return_value=Mock()) as create_credential,
    ):
        client = await authenticator.authenticate()

    assert client is fake_client
    create_credential.assert_called_once_with()
    fake_client.me.get.assert_awaited_once()

    call_kwargs = graph_client_cls.call_args.kwargs
    assert call_kwargs["credentials"] is authenticator._credential
    assert call_kwargs["scopes"] == ["scope"]
