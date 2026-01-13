"""Tests for database helpers."""

from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import create_async_engine

from src.database.models import EmailModel
from src.database.repository import build_async_db_url, get_session, init_db


def test_build_async_db_url_sqlite() -> None:
    """build_async_db_url should convert sqlite URLs to async URLs."""
    assert build_async_db_url("sqlite:///tmp/test.db") == "sqlite+aiosqlite:///tmp/test.db"
    assert build_async_db_url("sqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"


def test_build_async_db_url_passthrough() -> None:
    """build_async_db_url should leave non-sqlite URLs unchanged."""
    url = "postgresql://user:pass@localhost/db"
    assert build_async_db_url(url) == url


@pytest.mark.asyncio
async def test_init_db_creates_tables(tmp_path: Path) -> None:
    """init_db should create required tables."""
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'emails.db'}"
    engine = create_async_engine(db_url)

    await init_db(engine)

    async with engine.begin() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

    assert "emails" in tables
    assert "attachments" in tables
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_session_creates_tables(tmp_path: Path) -> None:
    """get_session should initialize tables and provide a session."""
    db_url = f"sqlite:///{tmp_path / 'session.db'}"

    async with get_session(db_url) as session:
        result = await session.execute(select(EmailModel))
        assert result.scalars().all() == []
