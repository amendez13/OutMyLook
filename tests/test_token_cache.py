"""Unit tests for src/auth/token_cache.py."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.auth.token_cache import TokenCache, TokenCacheError


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def test_save_and_load_token(tmp_path: Path) -> None:
    token_file = tmp_path / "token.json"
    cache = TokenCache(token_file)

    expires_on = _now_ts() + 3600
    asyncio.run(cache.save_token("abc123", expires_on, ["Mail.Read"]))

    # File should exist
    assert token_file.exists()

    # load_token should return the stored dict
    data = asyncio.run(cache.load_token())
    assert isinstance(data, dict)
    assert data["access_token"] == "abc123"
    assert data["expires_on"] == expires_on

    # has_valid_token should be True
    assert cache.has_valid_token() is True

    # get_access_token should return token
    assert asyncio.run(cache.get_access_token()) == "abc123"

    # get_token_info should return expected keys
    info = asyncio.run(cache.get_token_info())
    assert info is not None
    assert "expires_at" in info and "seconds_until_expiry" in info and "scopes" in info


def test_has_valid_token_missing_file(tmp_path: Path) -> None:
    token_file = tmp_path / "missing.json"
    cache = TokenCache(token_file)
    assert cache.has_valid_token() is False


def test_has_valid_token_missing_fields(tmp_path: Path) -> None:
    token_file = tmp_path / "token.json"
    # write only expires_on
    expires_on = _now_ts() + 3600
    token_file.write_text(json.dumps({"expires_on": expires_on}))

    cache = TokenCache(token_file)
    assert cache.has_valid_token() is False


def test_has_valid_token_expired(tmp_path: Path) -> None:
    token_file = tmp_path / "token.json"
    # expires soon (within buffer)
    expires_on = _now_ts() + 100
    token_file.write_text(json.dumps({"access_token": "x", "expires_on": expires_on}))

    cache = TokenCache(token_file)
    assert cache.has_valid_token() is False


def test_load_token_malformed_returns_none(tmp_path: Path) -> None:
    token_file = tmp_path / "token.json"
    token_file.write_text("not a json")

    cache = TokenCache(token_file)
    data = asyncio.run(cache.load_token())
    assert data is None


def test_save_token_raises_tokencacheerror_on_write_error(tmp_path: Path) -> None:
    token_file = tmp_path / "token.json"
    cache = TokenCache(token_file)

    # Patch the _write_token_file to raise
    with patch.object(TokenCache, "_write_token_file", side_effect=Exception("boom")):
        with pytest.raises(TokenCacheError):
            asyncio.run(cache.save_token("tok", _now_ts() + 1000, ["scope"]))


def test_clear_removes_file_and_errors(tmp_path: Path) -> None:
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({"access_token": "x", "expires_on": _now_ts() + 3600}))

    cache = TokenCache(token_file)
    # clear should remove the file
    asyncio.run(cache.clear())
    assert not token_file.exists()

    # calling clear when file does not exist should not raise
    asyncio.run(cache.clear())

    # simulate unlink raising
    cache2 = TokenCache(tmp_path / "token2.json")
    # create file and set unlink to raise by patching pathlib.Path.unlink
    f = tmp_path / "token2.json"
    f.write_text("{}")
    with patch("pathlib.Path.unlink", side_effect=Exception("boom")) as mock_unlink:
        with pytest.raises(TokenCacheError):
            asyncio.run(cache2.clear())
        assert mock_unlink.called


def test_is_token_expiring_soon_true_false(tmp_path: Path) -> None:
    token_file = tmp_path / "token.json"
    # soon
    expires_on_soon = _now_ts() + 100
    token_file.write_text(json.dumps({"access_token": "x", "expires_on": expires_on_soon}))
    cache = TokenCache(token_file)
    assert cache.is_token_expiring_soon() is True

    # later
    token_file.write_text(json.dumps({"access_token": "x", "expires_on": _now_ts() + 10000}))
    cache2 = TokenCache(token_file)
    assert cache2.is_token_expiring_soon() is False


def test_get_token_info_without_valid_token_returns_none(tmp_path: Path) -> None:
    token_file = tmp_path / "token.json"
    cache = TokenCache(token_file)
    assert asyncio.run(cache.get_token_info()) is None


def test_write_token_file_sets_permissions(tmp_path: Path) -> None:
    """_write_token_file should write file and set restrictive permissions."""
    token_file = tmp_path / "token.json"
    cache = TokenCache(token_file)

    # Patch Path.chmod to observe it being called
    with patch.object(Path, "chmod") as mock_chmod:
        cache._write_token_file({"access_token": "x", "expires_on": _now_ts() + 3600})

        # File should be created and chmod called with 0o600
        assert token_file.exists()
        mock_chmod.assert_called()


def test_load_token_read_raises_returns_none(tmp_path: Path) -> None:
    """If _read_token_file raises, load_token should return None."""
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({}))

    cache = TokenCache(token_file)

    with patch.object(TokenCache, "_read_token_file", side_effect=Exception("boom")):
        data = asyncio.run(cache.load_token())
        assert data is None


def test_has_valid_token_read_raises_returns_false(tmp_path: Path) -> None:
    """If _read_token_file raises, has_valid_token should return False."""
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({}))

    cache = TokenCache(token_file)

    with patch.object(TokenCache, "_read_token_file", side_effect=Exception("boom")):
        assert cache.has_valid_token() is False


def test_is_token_expiring_soon_on_read_error_returns_true(tmp_path: Path) -> None:
    """If reading token file fails, is_token_expiring_soon should return True."""
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({}))
    cache = TokenCache(token_file)

    with patch.object(TokenCache, "_read_token_file", side_effect=Exception("boom")):
        assert cache.is_token_expiring_soon() is True


def test_get_access_token_returns_none_when_invalid(tmp_path: Path) -> None:
    """When no valid token exists get_access_token should return None."""
    token_file = tmp_path / "token.json"
    cache = TokenCache(token_file)

    assert asyncio.run(cache.get_access_token()) is None
